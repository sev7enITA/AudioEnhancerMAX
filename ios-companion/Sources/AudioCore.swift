import Foundation

enum CompanionError: LocalizedError {
    case message(String)
    var errorDescription: String? { if case let .message(text) = self { return text }; return nil }
}

struct Wave: Sendable {
    var samples: [Float]
    let rate: Int
    let channels: Int
    var frames: Int { samples.count / channels }
    var duration: Double { Double(frames) / Double(rate) }
    static let maxBytes = 64 * 1024 * 1024

    init(samples: [Float], rate: Int, channels: Int) throws {
        guard (8000...96000).contains(rate), (1...2).contains(channels), !samples.isEmpty,
              samples.count % channels == 0, samples.count <= (Self.maxBytes-44)/4,
              samples.allSatisfy({ $0.isFinite }) else { throw CompanionError.message("Use bounded mono/stereo audio at 8–96 kHz.") }
        self.samples=samples; self.rate=rate; self.channels=channels
    }
    init(data: Data) throws {
        guard data.count >= 44, data.count <= Self.maxBytes,
              String(data:data.prefix(4),encoding:.ascii)=="RIFF",
              String(data:data[8..<12],encoding:.ascii)=="WAVE" else { throw CompanionError.message("Invalid or oversized WAV file.") }
        let b=[UInt8](data)
        func u16(_ p:Int)->Int { Int(b[p]) | Int(b[p+1]) << 8 }
        func u32(_ p:Int)->UInt32 { UInt32(b[p]) | UInt32(b[p+1])<<8 | UInt32(b[p+2])<<16 | UInt32(b[p+3])<<24 }
        guard Int(u32(4))+8 == b.count else { throw CompanionError.message("Incomplete WAV file.") }
        var pos=12, format:(Int,Int,Int,Int,Int,Int)?, payload:Range<Int>?
        while pos+8 <= b.count {
            let tag=String(bytes:b[pos..<pos+4],encoding:.ascii), size=Int(u32(pos+4)); pos+=8
            guard size<=b.count-pos else { throw CompanionError.message("Truncated WAV chunk.") }
            if tag=="fmt " {
                guard size>=16,format==nil else { throw CompanionError.message("Invalid WAV format.") }
                var kind=u16(pos)
                let bits=u16(pos+14)
                if kind==0xfffe {
                    let guidSuffix:[UInt8]=[0,0,0,0,0x10,0,0x80,0,0,0xaa,0,0x38,0x9b,0x71]
                    guard size>=40, u16(pos+16)>=22, 18+u16(pos+16)<=size, u16(pos+18)==bits,
                          b[(pos+26)..<(pos+40)].elementsEqual(guidSuffix) else {
                        throw CompanionError.message("Unsupported extended WAV format.")
                    }
                    kind=u16(pos+24)
                }
                format=(kind,u16(pos+2),Int(u32(pos+4)),Int(u32(pos+8)),u16(pos+12),bits)
            } else if tag=="data" {
                guard payload==nil else { throw CompanionError.message("Duplicate WAV data.") }
                payload=pos..<pos+size
            }
            pos+=size+(size%2)
        }
        guard pos==b.count else {throw CompanionError.message("Invalid WAV padding.")}
        guard let (kind,ch,sr,byteRate,align,bits)=format, let range=payload,
              (kind==1 && [16,24,32].contains(bits) || kind==3 && bits==32), (1...2).contains(ch),
              align==ch*bits/8, byteRate==sr*align, align>0, range.count%align==0 else {
            throw CompanionError.message("Use PCM16/24/32 or float32 WAV.")
        }
        var values=[Float](); values.reserveCapacity(range.count/(bits/8))
        for p in stride(from:range.lowerBound,to:range.upperBound,by:bits/8) {
            if kind==3 {
                values.append(Float(bitPattern:u32(p)))
            } else if bits==16 {
                values.append(Float(Int16(bitPattern:UInt16(u16(p))))/32768)
            } else if bits==24 {
                let packed=UInt32(b[p])<<8 | UInt32(b[p+1])<<16 | UInt32(b[p+2])<<24
                values.append(Float(Int32(bitPattern:packed))/2147483648)
            } else {
                values.append(Float(Int32(bitPattern:u32(p)))/2147483648)
            }
        }
        try self.init(samples:values,rate:sr,channels:ch)
    }
    /// Time bins include every frame and are cached before drawing the waveform.
    func overview(bins:Int=100)->[Float] {
        precondition((1...2048).contains(bins))
        return (0..<bins).map{i in
            let lo=i*frames/bins, hi=min(frames,max(lo+1,(i+1)*frames/bins))
            var peak:Float=0
            for j in lo*channels..<hi*channels {peak=max(peak,abs(samples[j]))}
            return min(1,peak)
        }
    }
    func encoded() -> Data {
        var data=Data()
        func word(_ v:UInt32,_ n:Int=4) { for i in 0..<n {data.append(UInt8(truncatingIfNeeded:v >> (8*i)))} }
        data.append(contentsOf:"RIFF".utf8); word(UInt32(36+samples.count*4)); data.append(contentsOf:"WAVEfmt ".utf8)
        word(16);word(3,2);word(UInt32(channels),2);word(UInt32(rate));word(UInt32(rate*channels*4));word(UInt32(channels*4),2);word(32,2)
        data.append(contentsOf:"data".utf8);word(UInt32(samples.count*4));for v in samples { word(v.bitPattern) };return data
    }
    func edited(start: Double, end: Double, gain: Double, normalize: Bool, voice: Bool) throws -> Wave {
        try render(StudioEdit(start: start, end: end, gain: gain, normalize: normalize, voice: voice)).wave
    }
    func autoEQ() throws -> Wave {
        var values=samples
        // Matched RBJ stages on Swift and Kotlin; never advertise other worker filters.
        let stages:[(String,Double,Double,Double)] = [("highpass",80,0.707,0),("lowShelf",150,0.707,1),("peak",250,1,-1.5),("peak",2500,1,1.5),("peak",5000,0.7,1),("highShelf",8000,0.707,0.5),("lowpass",16000,0.707,0)]
        for (kind,f,q,g) in stages {
            let w=2*Double.pi*min(f,Double(rate)*0.45)/Double(rate), c=cos(w), a=sin(w)/(2*q), A=pow(10,g/40), r=2*sqrt(A)*a
            let b0:Double,b1:Double,b2:Double,a0:Double,a1:Double,a2:Double
            switch kind {
            case "highpass": (b0,b1,b2,a0,a1,a2)=((1+c)/2,-(1+c),(1+c)/2,1+a,-2*c,1-a)
            case "lowpass": (b0,b1,b2,a0,a1,a2)=((1-c)/2,1-c,(1-c)/2,1+a,-2*c,1-a)
            case "lowShelf": (b0,b1,b2,a0,a1,a2)=(A*((A+1)-(A-1)*c+r),2*A*((A-1)-(A+1)*c),A*((A+1)-(A-1)*c-r),(A+1)+(A-1)*c+r,-2*((A-1)+(A+1)*c),(A+1)+(A-1)*c-r)
            case "highShelf": (b0,b1,b2,a0,a1,a2)=(A*((A+1)+(A-1)*c+r),-2*A*((A-1)+(A+1)*c),A*((A+1)+(A-1)*c-r),(A+1)-(A-1)*c+r,2*((A-1)-(A+1)*c),(A+1)-(A-1)*c-r)
            default: (b0,b1,b2,a0,a1,a2)=(1+a*A,-2*c,1-a*A,1+a/A,-2*c,1-a/A)
            }
            for ch in 0..<channels {
                var x1=0.0,x2=0.0,y1=0.0,y2=0.0
                for i in stride(from:ch,to:values.count,by:channels) {
                    let x=Double(values[i]), y=(b0*x+b1*x1+b2*x2-a1*y1-a2*y2)/a0
                    x2=x1;x1=x;y2=y1;y1=y;values[i]=Float(y)
                }
            }
        }
        return try Wave(samples:values,rate:rate,channels:channels)
    }
}

struct AudioComparison: Codable, Sendable {
    let sourceStart: Double
    let duration: Double
    let originalGain: Float
    let resultGain: Float

    func contains(_ position: Double) -> Bool {
        sourceStart <= position && position < sourceStart + duration
    }

    static func match(source: Wave, result: Wave, sourceStart: Double) -> Self? {
        guard sourceStart.isFinite, sourceStart >= 0, sourceStart <= source.duration,
              source.rate == result.rate, source.channels == result.channels else { return nil }
        let firstFrame = Int((sourceStart * Double(source.rate)).rounded())
        guard firstFrame <= source.frames - result.frames else { return nil }
        var sourceEnergy = 0.0
        var resultEnergy = 0.0
        for index in result.samples.indices {
            let original = Double(source.samples[firstFrame * source.channels + index])
            let revised = Double(result.samples[index])
            sourceEnergy += original * original
            resultEnergy += revised * revised
        }
        // Skip level matching for near silence. Only attenuate the louder player.
        let floor = Double(result.samples.count) * 1e-8
        let originalGain = resultEnergy > floor && sourceEnergy > resultEnergy ? sqrt(resultEnergy / sourceEnergy) : 1
        let resultGain = sourceEnergy > floor && resultEnergy > sourceEnergy ? sqrt(sourceEnergy / resultEnergy) : 1
        return Self(sourceStart: Double(firstFrame) / Double(source.rate), duration: result.duration,
                    originalGain: Float(originalGain), resultGain: Float(resultGain))
    }
}
