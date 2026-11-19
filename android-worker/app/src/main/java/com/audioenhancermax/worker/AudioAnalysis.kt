package com.audioenhancermax.worker

import kotlin.math.*
object AudioAnalysis {
    fun describe(wave:Wave,container:String,codec:String,bytes:Long,hash:String,remux:Boolean):String {
        var peak=0.0;var sum=0.0;var near=0;var dc=0.0
        for(sample in wave.samples){val x=sample.toDouble();peak=max(peak,abs(x));sum+=x*x;dc+=x;if(abs(x)>=0.999)near++}
        fun db(value:Double)=if(value>0)"%.1f dBFS".format(20*log10(value)) else "silence"
        return "Container: $container · Codec: $codec\n"+
            "%.2f s · %d Hz · %d channel(s) · %.2f MiB source\n".format(wave.duration,wave.rate,wave.channels,bytes/1048576.0)+
            "Decoded workspace: PCM float32 · no automatic resampling\n"+
            "Peak: ${db(peak)} · RMS: ${db(sqrt(sum/wave.samples.size))}\n"+
            "Near-full-scale samples: $near / ${wave.samples.size} · DC offset: %.5f\n".format(dc/wave.samples.size)+
            (if(near>0)"Check the loudest passages for clipping. " else "No samples at or above 99.9% full scale. ")+"RMS is not LUFS.\n"+
            (if(remux)"Video replacement available for this source.\n" else "Audio workspace ready; video replacement is not enabled for this source.\n")+
            "Original source SHA-256: $hash"
    }
}
