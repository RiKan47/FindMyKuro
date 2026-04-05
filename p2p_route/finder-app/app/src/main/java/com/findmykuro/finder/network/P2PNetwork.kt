package com.findmykuro.finder.network

import com.findmykuro.finder.crypto.CryptoManager
import io.libp2p.core.Host
import io.libp2p.core.PeerId
import io.libp2p.core.multiformats.Multiaddr
import io.libp2p.crypto.keys.Secp256K1Kt
import io.libp2p.etc.types.toByteArray
import io.libp2p.protocol.pubsub.PubsubApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.util.UUID

class P2PNetwork {

    private var host: Host? = null
    private var pubsubApi: PubsubApi? = null

    companion object {
        const val TOPIC_NAME = "/findmykuro/locations/v1"
        const val BOOTSTRAP_NODE = "/ip4/127.0.0.1/tcp/4001"
    }

    suspend fun startNode() = withContext(Dispatchers.IO) {
        val keyPair = Secp256K1Kt.generateKeyPair()

        host = Host.Builder()
            .privateKey(keyPair.privateKey)
            .listenAddresses(
                Multiaddr.fromString("/ip4/0.0.0.0/tcp/0"),
                Multiaddr.fromString("/ip4/0.0.0.0/udp/0/quic-v1")
            )
            .build()

        host?.start()?.await()

        pubsubApi = PubsubApi(host!!)
        pubsubApi?.subscribe(TOPIC_NAME)

        host?.listen()?.await()
    }

    suspend fun publishLocation(
        eid: ByteArray,
        encryptedLocation: CryptoManager.EncryptedLocation,
        rssi: Int
    ) = withContext(Dispatchers.IO) {
        val payload = JSONObject().apply {
            put("eid", eid.toHexString())
            put("encrypted_payload", encryptedLocation.encryptedPayload.toHexString())
            put("iv", encryptedLocation.iv.toHexString())
            put("rssi", rssi)
            put("timestamp", System.currentTimeMillis())
            put("finder_id", UUID.randomUUID().toString())
        }

        pubsubApi?.publish(TOPIC_NAME, payload.toString().toByteArray(Charsets.UTF_8))
    }

    suspend fun subscribeToLocations(callback: (LocationReport) -> Unit) = withContext(Dispatchers.IO) {
        pubsubApi?.subscribe(TOPIC_NAME)?.consumeEach { message ->
            val data = String(message.data.toByteArray(), Charsets.UTF_8)
            val json = JSONObject(data)

            val report = LocationReport(
                eid = json.getString("eid").hexToByteArray(),
                encryptedPayload = json.getString("encrypted_payload").hexToByteArray(),
                iv = json.getString("iv").hexToByteArray(),
                rssi = json.getInt("rssi"),
                timestamp = json.getLong("timestamp"),
                finderId = json.getString("finder_id")
            )

            callback(report)
        }
    }

    suspend fun stopNode() = withContext(Dispatchers.IO) {
        host?.stop()?.await()
        host = null
        pubsubApi = null
    }

    data class LocationReport(
        val eid: ByteArray,
        val encryptedPayload: ByteArray,
        val iv: ByteArray,
        val rssi: Int,
        val timestamp: Long,
        val finderId: String
    )

    private fun ByteArray.toHexString(): String =
        joinToString("") { "%02x".format(it) }

    private fun String.hexToByteArray(): ByteArray {
        val result = ByteArray(length / 2)
        for (i in indices step 2) {
            result[i / 2] = substring(i, i + 2).toInt(16).toByte()
        }
        return result
    }
}
