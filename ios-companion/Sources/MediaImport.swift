import Foundation
import AVFoundation
import CryptoKit
import UniformTypeIdentifiers

/// Picker types are hints. Check the bytes and then let the native decoder validate the stream.
enum MediaImportPolicy {
    enum Kind { case wav, mp3, mp4, aac, flac, caf, aiff, ogg, amr }
    enum Filter:String,CaseIterable,Identifiable,Sendable {
        case all, wav, mp3, m4a, flac, cafAiff, video
        var id:String {rawValue}
        var label:String {
            switch self {
            case .all:return "All supported"
            case .wav:return "WAV"
            case .mp3:return "MP3"
            case .m4a:return "M4A / AAC"
            case .flac:return "FLAC"
            case .cafAiff:return "CAF / AIFF"
            case .video:return "Video · MP4 / MOV"
            }
        }
        var contentTypes:[UTType] {
            let extensions:[String]
            switch self {
            case .all:return [.audio,.movie]
            case .wav:extensions=["wav"]
            case .mp3:extensions=["mp3"]
            case .m4a:extensions=["m4a","aac"]
            case .flac:extensions=["flac"]
            case .cafAiff:extensions=["caf","aif","aiff"]
            case .video:extensions=["mp4","mov","3gp"]
            }
            return extensions.compactMap{UTType(filenameExtension:$0)}
        }
        func accepts(_ kind:Kind,hasVideo:Bool=false)->Bool {
            switch self {
            case .all:return true
            case .wav:return kind == .wav && !hasVideo
            case .mp3:return kind == .mp3 && !hasVideo
            case .m4a:return (kind == .mp4 || kind == .aac) && !hasVideo
            case .flac:return kind == .flac && !hasVideo
            case .cafAiff:return (kind == .caf || kind == .aiff) && !hasVideo
            case .video:return kind == .mp4 && hasVideo
            }
        }
        func validate(_ kind:Kind,hasVideo:Bool=false) throws {
            guard accepts(kind,hasVideo:hasVideo) else {throw CompanionError.message("This file does not match \(label). Choose the matching import format or All supported. Your previous recording is preserved.")}
        }
    }
    static let videoMaxBytes = 100 * 1024 * 1024
    static func classify(_ data: Data) throws -> Kind {
        let b = [UInt8](data)
        func tag(_ offset: Int, _ text: String) -> Bool {
            b.count >= offset + text.utf8.count && Array(b[offset..<offset+text.utf8.count]) == Array(text.utf8)
        }
        if tag(0,"RIFF") && tag(8,"WAVE") { return .wav }
        if tag(0,"ID3") { return .mp3 }
        if b.count >= 4, b[0] == 255, b[1] & 224 == 224, b[1] & 24 != 8,
           b[1] & 6 == 2, b[2] & 240 != 240, b[2] & 240 != 0, b[2] & 12 != 12 { return .mp3 }
        if tag(4,"ftyp") { return .mp4 }
        if tag(0,"fLaC"){return .flac}
        if tag(0,"caff"){return .caf}
        if tag(0,"FORM") && (tag(8,"AIFF") || tag(8,"AIFC")){return .aiff}
        if tag(0,"OggS"){return .ogg}
        if tag(0,"#!AMR"){return .amr}
        if b.count>=2, b[0]==255, b[1] & 246 == 240{return .aac}
        throw CompanionError.message("Unsupported container. Choose a smartphone recording such as M4A/AAC, WAV, MP3, FLAC, CAF, AIFF, MP4 or MOV. Codec availability is checked locally.")
    }
    static func validateReplacement(_ result: Wave, source: Wave) throws {
        guard result.rate == source.rate, result.channels == source.channels, result.frames == source.frames else {
            throw CompanionError.message("To keep the video synchronized, improve the full audio without trimming. Export a trimmed result as WAV instead.")
        }
    }
}

struct ImportedMedia: Sendable {
    let wave: Wave
    /// An owned, unique private copy. Caller removes it on failure or when replacing the workspace.
    let video: URL?
    let analysis:String
    let overview:[Float]
}

enum MediaImport {
    static func read(_ url: URL, folder: URL, filter:MediaImportPolicy.Filter = .all) async throws -> ImportedMedia {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        let kind = try MediaImportPolicy.classify(try handle.read(upToCount: 64) ?? Data())
        let limit=MediaImportPolicy.videoMaxBytes
        guard let size=try url.resourceValues(forKeys:[.fileSizeKey]).fileSize,size>0,size<=limit else {throw CompanionError.message("Source exceeds the 100 MiB import limit.")}
        let asset=AVURLAsset(url:url)
        let hasVideo = !(try await asset.loadTracks(withMediaType:.video)).isEmpty
        try filter.validate(kind,hasVideo:hasVideo)
        let tracks=try await asset.loadTracks(withMediaType:.audio)
        guard tracks.count==1 else{throw CompanionError.message("No single decodable audio track found. iOS may not support this container/codec. Export M4A/AAC or WAV from the recorder. No audio was uploaded.")}
        let track=tracks[0]
        let wave:Wave
        if kind == .wav,let pcm=try? Wave(data:Data(contentsOf:url)){wave=pcm}
        else{wave=try await readVideoAudio(asset,track:track)}
        let format=try await track.load(.formatDescriptions).first
        let subtype=format.map{CMFormatDescriptionGetMediaSubType($0)} ?? 0
        let codec=String(bytes:[UInt8((subtype>>24)&255),UInt8((subtype>>16)&255),UInt8((subtype>>8)&255),UInt8(subtype&255)],encoding:.ascii) ?? "unknown"
        let bitrate=try await track.load(.estimatedDataRate)
        var hasher=SHA256();try handle.seek(toOffset:0)
        while let chunk=try handle.read(upToCount:65536),!chunk.isEmpty{try Task.checkCancellation();hasher.update(data:chunk)}
        let hash=hasher.finalize().map{String(format:"%02x",$0)}.joined()
        let canRemux=(try? await videoTracks(asset)) != nil
        var copy:URL?
        if canRemux {
            let target=folder.appendingPathComponent("source-\(UUID().uuidString).mp4")
            do{try FileManager.default.copyItem(at:url,to:target);copy=target}catch{try? FileManager.default.removeItem(at:target);throw error}
        }
        let analysis=AudioAnalysis.describe(wave,container:"\(kind) (\(url.pathExtension.lowercased()))",codec:codec,bitrate:bitrate,bytes:size,hash:hash,remux:canRemux)
        return ImportedMedia(wave:wave,video:copy,analysis:analysis,overview:wave.overview())
    }
    static func videoTracks(_ asset: AVAsset) async throws -> (video: AVAssetTrack, audio: AVAssetTrack) {
        let video = try await asset.loadTracks(withMediaType:.video), audio = try await asset.loadTracks(withMediaType:.audio)
        guard video.count == 1, audio.count == 1 else {throw CompanionError.message("Choose MP4 with exactly one video track and one audio track.")}
        let vf = try await video[0].load(.formatDescriptions), af = try await audio[0].load(.formatDescriptions)
        guard vf.count == 1, af.count == 1, CMFormatDescriptionGetMediaSubType(vf[0]) == kCMVideoCodecType_H264,
              CMFormatDescriptionGetMediaSubType(af[0]) == kAudioFormatMPEG4AAC else {
            throw CompanionError.message("This preview supports MP4 with H.264 video and AAC audio. Convert other codecs first.")
        }
        return (video[0],audio[0])
    }
    private static func readVideoAudio(_ asset: AVAsset, track: AVAssetTrack) async throws -> Wave {
        let descriptions = try await track.load(.formatDescriptions)
        guard let format = descriptions.first, let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(format) else {throw CompanionError.message("Missing audio format.")}
        let channels = Int(asbd.pointee.mChannelsPerFrame), rate = Int(asbd.pointee.mSampleRate)
        guard (1...2).contains(channels), (8000...96000).contains(rate) else {throw CompanionError.message("Use mono/stereo audio at 8–96 kHz.")}
        let range = try await track.load(.timeRange)
        let frameLength = range.duration.seconds * Double(rate)
        guard range.start.seconds.isFinite, frameLength.isFinite, frameLength > 0,
              frameLength <= Double((Wave.maxBytes-44)/(4*channels)) else {throw CompanionError.message("Decoded audio exceeds 64 MiB (about 3 minutes of stereo at 48 kHz or 17 minutes of mono at 16 kHz). Choose a shorter recording.")}
        let frameCount = Int(frameLength.rounded())
        let reader = try AVAssetReader(asset:asset)
        let output = AVAssetReaderTrackOutput(track:track,outputSettings:[AVFormatIDKey:kAudioFormatLinearPCM,AVLinearPCMBitDepthKey:32,AVLinearPCMIsFloatKey:true,AVLinearPCMIsBigEndianKey:false,AVLinearPCMIsNonInterleaved:false])
        guard reader.canAdd(output) else {throw CompanionError.message("Cannot decode this audio track.")}
        reader.add(output)
        guard reader.startReading() else {throw reader.error ?? CompanionError.message("Cannot open MP4 audio.")}
        defer {reader.cancelReading()}
        var samples = [Float](repeating:0,count:frameCount*channels), received = false, previousEnd = 0
        let deadline = Date().addingTimeInterval(180)
        while let buffer = output.copyNextSampleBuffer() {
            try Task.checkCancellation()
            guard Date() < deadline, let block = CMSampleBufferGetDataBuffer(buffer) else {throw CompanionError.message("Audio extraction timed out or returned invalid data.")}
            let pts = CMSampleBufferGetPresentationTimeStamp(buffer).seconds
            let startFrameValue = (pts-range.start.seconds)*Double(rate)
            guard startFrameValue.isFinite, abs(startFrameValue) < Double(Int.max/4) else {throw CompanionError.message("Invalid audio timestamp.")}
            let startFrame = Int(startFrameValue.rounded())
            let size = CMBlockBufferGetDataLength(block), frames = size/(4*channels)
            guard size > 0, size % (4*channels) == 0, size <= Wave.maxBytes,
                  startFrame >= -4096, startFrame <= frameCount+4096,
                  !received || startFrame >= previousEnd-1 else {throw CompanionError.message("Invalid or overlapping audio timeline.")}
            var data = Data(count:size)
            let status = data.withUnsafeMutableBytes {CMBlockBufferCopyDataBytes(block,atOffset:0,dataLength:size,destination:$0.baseAddress!)}
            guard status == kCMBlockBufferNoErr else {throw CompanionError.message("Cannot read decoded audio.")}
            // Preserve leading, internal and trailing gaps as silence. Trim codec priming/padding
            // to the declared track interval rather than concatenating packets and shifting sync.
            let lo=max(0,-startFrame), hi=max(0,min(frames,frameCount-startFrame))
            if hi > lo {data.withUnsafeBytes { raw in
                for frame in lo..<hi {
                    for channel in 0..<channels {
                        let index=frame*channels+channel
                        samples[(startFrame+frame)*channels+channel]=Float(bitPattern:UInt32(littleEndian:raw.loadUnaligned(fromByteOffset:index*4,as:UInt32.self)))
                    }
                }
            }}
            received = received || hi > lo;previousEnd = startFrame+frames
        }
        guard reader.status == .completed, received else {throw reader.error ?? CompanionError.message("Incomplete MP4 audio.")}
        return try Wave(samples:samples,rate:rate,channels:channels)
    }
    static func replaceAudio(video: URL, result: URL, source: Wave, output: URL) async throws {
        let edited=try Wave(data:Data(contentsOf:result))
        try MediaImportPolicy.validateReplacement(edited,source:source)
        let original=AVURLAsset(url:video), audioAsset=AVURLAsset(url:result)
        let tracks=try await videoTracks(original)
        let videoRange=try await tracks.video.load(.timeRange), audioRange=try await tracks.audio.load(.timeRange)
        guard abs(audioRange.duration.seconds-source.duration) < 0.002,
              let audioTrack=try await audioAsset.loadTracks(withMediaType:.audio).first,
              let videoFormat=try await tracks.video.load(.formatDescriptions).first else {throw CompanionError.message("Audio duration does not match the video track. Export WAV instead.")}
        let videoReader=try AVAssetReader(asset:original), audioReader=try AVAssetReader(asset:audioAsset)
        let videoOutput=AVAssetReaderTrackOutput(track:tracks.video,outputSettings:nil)
        let audioOutput=AVAssetReaderTrackOutput(track:audioTrack,outputSettings:[AVFormatIDKey:kAudioFormatLinearPCM,AVLinearPCMBitDepthKey:32,AVLinearPCMIsFloatKey:true,AVLinearPCMIsNonInterleaved:false])
        guard videoReader.canAdd(videoOutput),audioReader.canAdd(audioOutput) else {throw CompanionError.message("Cannot read media for export.")}
        videoReader.add(videoOutput);audioReader.add(audioOutput)
        let writer=try AVAssetWriter(outputURL:output,fileType:.mp4)
        let videoInput=AVAssetWriterInput(mediaType:.video,outputSettings:nil,sourceFormatHint:videoFormat)
        videoInput.transform=try await tracks.video.load(.preferredTransform)
        let audioInput=AVAssetWriterInput(mediaType:.audio,outputSettings:[AVFormatIDKey:kAudioFormatMPEG4AAC,AVSampleRateKey:source.rate,AVNumberOfChannelsKey:source.channels,AVEncoderBitRateKey:source.channels == 1 ? 128000:192000])
        guard writer.canAdd(videoInput),writer.canAdd(audioInput) else {throw CompanionError.message("This device cannot encode this MP4.")}
        writer.add(videoInput);writer.add(audioInput)
        do {
            guard writer.startWriting(),videoReader.startReading(),audioReader.startReading() else {throw writer.error ?? videoReader.error ?? audioReader.error ?? CompanionError.message("Cannot start video export.")}
            writer.startSession(atSourceTime:.zero)
            var videoDone=false,audioDone=false
            let deadline=Date().addingTimeInterval(60)
            while !videoDone || !audioDone {
                try Task.checkCancellation()
                guard Date() < deadline,writer.status == .writing else {throw writer.error ?? CompanionError.message("Video export timed out.")}
                var progressed=false
                if !videoDone,videoInput.isReadyForMoreMediaData {
                    if let sample=videoOutput.copyNextSampleBuffer() {
                        guard videoInput.append(sample) else {throw writer.error ?? CompanionError.message("Cannot copy video frame.")}
                    } else {
                        guard videoReader.status == .completed else {throw videoReader.error ?? CompanionError.message("Incomplete video track.")}
                        videoInput.markAsFinished();videoDone=true
                    }
                    progressed=true
                }
                if !audioDone,audioInput.isReadyForMoreMediaData {
                    if let sample=audioOutput.copyNextSampleBuffer() {
                        var timing=CMSampleTimingInfo(duration:CMTime(value:1,timescale:CMTimeScale(source.rate)),presentationTimeStamp:CMTimeAdd(CMSampleBufferGetPresentationTimeStamp(sample),audioRange.start),decodeTimeStamp:.invalid)
                        var shifted:CMSampleBuffer?
                        let status=CMSampleBufferCreateCopyWithNewTiming(allocator:kCFAllocatorDefault,sampleBuffer:sample,sampleTimingEntryCount:1,sampleTimingArray:&timing,sampleBufferOut:&shifted)
                        guard status == noErr,let shifted,audioInput.append(shifted) else {throw writer.error ?? CompanionError.message("Cannot encode replacement audio.")}
                    } else {
                        guard audioReader.status == .completed else {throw audioReader.error ?? CompanionError.message("Incomplete replacement audio.")}
                        audioInput.markAsFinished();audioDone=true
                    }
                    progressed=true
                }
                if !progressed {try await Task.sleep(for:.milliseconds(2))}
            }
            writer.endSession(atSourceTime:CMTimeMaximum(CMTimeRangeGetEnd(videoRange),CMTimeRangeGetEnd(audioRange)))
            await writer.finishWriting()
            guard writer.status == .completed else {throw writer.error ?? CompanionError.message("Incomplete MP4 export.")}
        } catch {
            videoReader.cancelReading();audioReader.cancelReading();writer.cancelWriting()
            try? FileManager.default.removeItem(at:output);throw error
        }
    }
}
