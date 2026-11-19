import Foundation

enum AudioAnalysis {
    static func describe(_ wave:Wave,container:String,codec:String,bitrate:Float,bytes:Int,hash:String,remux:Bool)->String {
        var peak=0.0,sum=0.0,dc=0.0,near=0
        for sample in wave.samples{let x=Double(sample);peak=max(peak,abs(x));sum+=x*x;dc+=x;if abs(x)>=0.999{near+=1}}
        func db(_ value:Double)->String{value>0 ? String(format:"%.1f dBFS",20*log10(value)):"silence"}
        let rate=bitrate>0 ? String(format:"%.0f kbps estimated",bitrate/1000):"bitrate unavailable"
        return "Container: \(container) · Codec: \(codec) · \(rate)\n" +
            String(format:"%.2f s · %d Hz · %d channel(s) · %.2f MiB source\n",wave.duration,wave.rate,wave.channels,Double(bytes)/1048576) +
            "Decoded workspace: PCM float32 · no automatic resampling\nPeak: \(db(peak)) · RMS: \(db(sqrt(sum/Double(wave.samples.count))))\nNear-full-scale samples: \(near) / \(wave.samples.count) · DC offset: \(String(format:"%.5f",dc/Double(wave.samples.count)))\n" +
            (near>0 ? "Check loud passages for clipping. " : "No samples at or above 99.9% full scale. ")+"RMS is not LUFS.\n" +
            (remux ? "Video replacement available.\n" : "Audio workspace ready; video replacement is not enabled for this source.\n")+"Original source SHA-256: \(hash)"
    }
}
