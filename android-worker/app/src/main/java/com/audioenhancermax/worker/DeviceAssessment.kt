package com.audioenhancermax.worker

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.PowerManager
import android.os.SystemClock
import android.util.Base64
import com.google.gson.Gson
import java.time.Instant
import kotlin.math.sin

/** A bounded DSP measurement, never an estimate of general AI performance. */
object DeviceAssessment {
    @Volatile private var measuredMs:Double?=null
    @Volatile private var measuredAt:String?=null
    @Volatile var roundTripMs:Long?=null
    fun benchmark() {
        val wave=Wave(FloatArray(96000){(0.2*sin(2*Math.PI*440*it/48000)).toFloat()},48000,1)
        wave.autoEQ() // warm up the same production implementation
        val times=(0..2).map {
            val start=SystemClock.elapsedRealtimeNanos()
            val result=wave.autoEQ()
            check(result.samples.size==96000 && result.samples.all{it.isFinite()})
            (SystemClock.elapsedRealtimeNanos()-start)/1000000.0
        }.sorted()
        measuredMs=times[1];measuredAt=Instant.now().toString()
    }
    fun snapshot(context:Context):Map<String,Any> {
        val memory=ActivityManager.MemoryInfo();context.getSystemService(ActivityManager::class.java).getMemoryInfo(memory)
        val battery=context.registerReceiver(null,IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level=battery?.getIntExtra(BatteryManager.EXTRA_LEVEL,-1) ?: -1
        val scale=battery?.getIntExtra(BatteryManager.EXTRA_SCALE,-1) ?: -1
        val power=context.getSystemService(PowerManager::class.java)
        val thermal=if(Build.VERSION.SDK_INT>=29) when(power.currentThermalStatus){0->"nominal";1->"light";2->"moderate";3->"severe";4->"critical";5->"emergency";else->"shutdown"} else "unavailable"
        return mutableMapOf<String,Any>("schema" to 1,"model" to "${Build.MANUFACTURER} ${Build.MODEL}","os" to "Android ${Build.VERSION.RELEASE}","ram_bytes" to memory.totalMem,"available_bytes" to memory.availMem,"thermal" to thermal,"charging" to ((battery?.getIntExtra(BatteryManager.EXTRA_PLUGGED,0) ?: 0)>0)).apply {
            if(level>=0 && scale>0)put("battery_percent",level*100/scale)
            measuredMs?.let{put("voice_eq_ms",it);put("benchmark","voice-eq-2s-48k-mono-v1");put("benchmark_at",measuredAt ?: "")}
            roundTripMs?.let{put("round_trip_ms",it)}
        }
    }
    fun header(context:Context)=Base64.encodeToString(Gson().toJson(snapshot(context)).toByteArray(),Base64.NO_WRAP)
    fun summary(context:Context):String {
        val a=snapshot(context)
        val ms=measuredMs
        return "${a["model"]} · ${a["os"]}\n${Runtime.getRuntime().availableProcessors()} logical cores · %.1f GiB RAM · %.1f GiB available".format((a["ram_bytes"] as Long)/1073741824.0,(a["available_bytes"] as Long)/1073741824.0)+
            "\nBattery ${a["battery_percent"] ?: "unavailable"}% · Thermal state: ${a["thermal"]}\n"+
            (ms?.let{"Voice EQ: %.1f ms for 2 s mono / 48 kHz (median of 3).\n".format(it)+(if(it<2000)"Suitable for foreground Voice EQ." else "Prefer Mac processing for this workload.")} ?: "Voice EQ has not been measured yet.")+"\nLocal DSP only. Network overhead is excluded. No AI-model capability is inferred."
    }
}
