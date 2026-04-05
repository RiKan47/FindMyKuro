package com.findmykuro.finder.crypto

import org.bouncycastle.jce.ECNamedCurveTable
import org.bouncycastle.jce.spec.ECNamedCurveParameterSpec
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.Security
import javax.crypto.Cipher
import javax.crypto.spec.IvParameterSpec
import javax.crypto.spec.SecretKeySpec

object CryptoManager {

    init {
        Security.addProvider(org.bouncycastle.jce.provider.BouncyCastleProvider())
    }

    private const val CURVE_NAME = "secp160r1"
    private const val ALGORITHM = "ECIES"
    private const val SYMMETRIC_ALGORITHM = "AES"
    private const val AES_MODE = "AES/CTR/NoPadding"

    fun generateKeyPair(): KeyPair {
        val keyPairGen = KeyPairGenerator.getInstance("EC", "BC")
        val ecSpec: ECNamedCurveParameterSpec = ECNamedCurveTable.getParameterSpec(CURVE_NAME)
        keyPairGen.initialize(ecSpec, java.security.SecureRandom())
        return keyPairGen.generateKeyPair()
    }

    fun deriveSharedSecret(privateKey: java.security.PrivateKey, publicKey: java.security.PublicKey): ByteArray {
        val keyAgreement = javax.crypto.KeyAgreement.getInstance("ECDH", "BC")
        keyAgreement.init(privateKey)
        keyAgreement.doPhase(publicKey, true)
        return keyAgreement.generateSecret()
    }

    fun encryptLocation(
        latitude: Double,
        longitude: Double,
        accuracy: Float,
        trackerPublicKey: java.security.PublicKey,
        finderPrivateKey: java.security.PrivateKey
    ): EncryptedLocation {
        val sharedSecret = deriveSharedSecret(finderPrivateKey, trackerPublicKey)

        val keySpec = SecretKeySpec(sharedSecret.copyOf(16), SYMMETRIC_ALGORITHM)
        val iv = ByteArray(16)
        java.security.SecureRandom().nextBytes(iv)

        val cipher = Cipher.getInstance(AES_MODE, "BC")
        cipher.init(Cipher.ENCRYPT_MODE, keySpec, IvParameterSpec(iv))

        val locationJson = "{\"lat\":$latitude,\"lon\":$longitude,\"acc\":$accuracy,\"ts\":${System.currentTimeMillis()}}"
        val encryptedData = cipher.doFinal(locationJson.toByteArray(Charsets.UTF_8))

        return EncryptedLocation(
            encryptedPayload = encryptedData,
            iv = iv,
            ephemeralPublicKey = finderPrivateKey.public as java.security.PublicKey
        )
    }

    fun decryptLocation(
        encryptedData: ByteArray,
        iv: ByteArray,
        sharedSecret: ByteArray
    ): String {
        val keySpec = SecretKeySpec(sharedSecret.copyOf(16), SYMMETRIC_ALGORITHM)
        val cipher = Cipher.getInstance(AES_MODE, "BC")
        cipher.init(Cipher.DECRYPT_MODE, keySpec, IvParameterSpec(iv))
        return String(cipher.doFinal(encryptedData), Charsets.UTF_8)
    }

    data class EncryptedLocation(
        val encryptedPayload: ByteArray,
        val iv: ByteArray,
        val ephemeralPublicKey: java.security.PublicKey
    ) {
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (javaClass != other?.javaClass) return false
            other as EncryptedLocation
            if (!encryptedPayload.contentEquals(other.encryptedPayload)) return false
            if (!iv.contentEquals(other.iv)) return false
            if (ephemeralPublicKey != other.ephemeralPublicKey) return false
            return true
        }

        override fun hashCode(): Int {
            var result = encryptedPayload.contentHashCode()
            result = 31 * result + iv.contentHashCode()
            result = 31 * result + ephemeralPublicKey.hashCode()
            return result
        }
    }
}
