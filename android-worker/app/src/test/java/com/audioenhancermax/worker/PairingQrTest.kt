package com.audioenhancermax.worker

import com.google.zxing.BinaryBitmap
import com.google.zxing.RGBLuminanceSource
import com.google.zxing.common.HybridBinarizer
import com.google.zxing.qrcode.QRCodeReader
import org.junit.Assert.*
import org.junit.Test

class PairingQrTest {
    @Test fun readsMacGeneratedQrAndValidatesPairing() {
        // PGM pixels from the Mac QR encoder; no Android camera or desktop AWT mock.
        val image=javaClass.getResourceAsStream("/pairing-fixture.pgm")!!.readBytes()
        var offset=0
        fun line():String { val start=offset;while(image[offset]!=10.toByte())offset++;return String(image,start,offset++-start) }
        assertEquals("P5",line())
        val dimensions=line().split(" ").map{it.toInt()};assertEquals("255",line())
        val pixels=IntArray(dimensions[0]*dimensions[1]) { i -> (image[offset+i].toInt() and 255)*0x010101 }
        val decoded=QRCodeReader().decode(BinaryBitmap(HybridBinarizer(RGBLuminanceSource(dimensions[0],dimensions[1],pixels)))).text
        val expected=javaClass.getResourceAsStream("/pairing-fixture.json")!!.bufferedReader().readText()
        assertEquals(Pairing.parse(expected),Pairing.parse(decoded))
    }
    @Test fun rejectsUnrelatedAndOversizedQrContents() {
        for(raw in listOf("https://example.com","{}","x".repeat(4096))) {
            assertTrue(runCatching{Pairing.parse(raw)}.isFailure)
        }
    }
}
