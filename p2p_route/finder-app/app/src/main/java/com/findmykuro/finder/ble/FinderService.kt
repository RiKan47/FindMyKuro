package com.findmykuro.finder.ble

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.bluetooth.le.BluetoothLeScanner
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.ParcelUuid
import androidx.core.app.NotificationCompat
import androidx.lifecycle.LifecycleService
import androidx.lifecycle.lifecycleScope
import com.findmykuro.finder.R
import com.findmykuro.finder.crypto.CryptoManager
import com.findmykuro.finder.network.P2PNetwork
import com.findmykuro.finder.ui.MainActivity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.UUID

class FinderService : LifecycleService() {

    private var bluetoothLeScanner: BluetoothLeScanner? = null
    private var isScanning = false

    private val p2pNetwork = P2PNetwork()

    companion object {
        const val CHANNEL_ID = "findmykuro_finder_channel"
        const val NOTIFICATION_ID = 1
        const val FMDN_SERVICE_UUID = "0000feaa-0000-1000-8000-00805f9b34fb"
        const val FINDMYKURO_SERVICE_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

        private var scanCallback: ScanCallback? = null
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
        initializeP2P()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        startScanning()
        return START_STICKY
    }

    override fun onDestroy() {
        super.onDestroy()
        stopScanning()
    }

    private fun initializeP2P() {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                p2pNetwork.startNode()
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    updateNotification("P2P network init failed: ${e.message}")
                }
            }
        }
    }

    @SuppressLint("MissingPermission")
    private fun startScanning() {
        val bluetoothManager = getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
        val adapter = bluetoothManager.adapter
        if (adapter == null || !adapter.isEnabled) {
            updateNotification("Bluetooth is not enabled")
            return
        }

        bluetoothLeScanner = adapter.bluetoothLeScanner
        if (bluetoothLeScanner == null) {
            updateNotification("BLE not supported")
            return
        }

        val serviceUuid = ParcelUuid.fromString("0000feaa-0000-1000-8000-00805f9b34fb")
        val filters = listOf(
            ScanFilter.Builder().setServiceUuid(serviceUuid).build()
        )

        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_POWER)
            .setReportDelay(0)
            .apply {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    setMatchMode(ScanSettings.MATCH_MODE_AGGRESSIVE)
                }
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    setLegacy(false)
                    setPhy(ScanSettings.PHY_LE_ALL_SUPPORTED)
                }
            }
            .build()

        scanCallback = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult) {
                handleScanResult(result)
            }

            override fun onBatchScanResults(results: MutableList<ScanResult>) {
                results.forEach { handleScanResult(it) }
            }

            override fun onScanFailed(errorCode: Int) {
                updateNotification("Scan failed with error: $errorCode")
            }
        }

        if (!isScanning) {
            bluetoothLeScanner?.startScan(filters, settings, scanCallback!!)
            isScanning = true
            updateNotification("Scanning for FindMyKuro beacons...")
        }
    }

    @SuppressLint("MissingPermission")
    private fun stopScanning() {
        if (isScanning && bluetoothLeScanner != null) {
            bluetoothLeScanner?.stopScan(scanCallback)
            isScanning = false
        }
    }

    private fun handleScanResult(result: ScanResult) {
        val scanRecord = result.scanRecord ?: return
        val serviceData = scanRecord.serviceData

        serviceData.forEach { (uuid, data) ->
            if (isFindMyKuroBeacon(uuid, data)) {
                lifecycleScope.launch(Dispatchers.IO) {
                    processBeacon(result, data)
                }
            }
        }
    }

    private fun isFindMyKuroBeacon(uuid: ParcelUuid, data: ByteArray): Boolean {
        if (data.size < 8) return false

        val expectedUuid = UUID.fromString(FMDN_SERVICE_UUID)
        if (uuid.uuid != expectedUuid) return false

        val frameType = data[3]
        return frameType == 0x40.toByte() || frameType == 0x41.toByte()
    }

    private suspend fun processBeacon(result: ScanResult, data: ByteArray) {
        val eid = data.copyOfRange(4, 24)
        val rssi = result.rssi
        val deviceAddress = result.device?.address ?: return

        updateNotification("Found beacon: ${eid.toHexString().take(16)}...")

        val location = getLastKnownLocation() ?: return

        val encryptedLocation = CryptoManager.encryptLocation(
            latitude = location.latitude,
            longitude = location.longitude,
            accuracy = location.accuracy,
            trackerPublicKey = CryptoManager.generateKeyPair().public,
            finderPrivateKey = CryptoManager.generateKeyPair().private
        )

        p2pNetwork.publishLocation(
            eid = eid,
            encryptedLocation = encryptedLocation,
            rssi = rssi
        )

        withContext(Dispatchers.Main) {
            updateNotification("Location published for beacon: ${eid.toHexString().take(16)}...")
        }
    }

    private fun getLastKnownLocation(): android.location.Location? {
        val locationManager = getSystemService(Context.LOCATION_SERVICE) as android.location.LocationManager
        return try {
            locationManager.getLastKnownLocation(android.location.LocationManager.GPS_PROVIDER)
                ?: locationManager.getLastKnownLocation(android.location.LocationManager.NETWORK_PROVIDER)
        } catch (e: SecurityException) {
            null
        }
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            "FindMyKuro Finder Service",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Scans for FindMyKuro beacons and reports locations"
        }

        val notificationManager = getSystemService(NotificationManager::class.java)
        notificationManager.createNotificationChannel(channel)
    }

    private fun buildNotification(): Notification {
        val intent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("FindMyKuro Finder")
            .setContentText("Scanning for nearby beacons...")
            .setSmallIcon(R.drawable.ic_notification)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(text: String) {
        val notificationManager = getSystemService(NotificationManager::class.java)
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("FindMyKuro Finder")
            .setContentText(text)
            .setSmallIcon(R.drawable.ic_notification)
            .setOngoing(true)
            .build()

        notificationManager.notify(NOTIFICATION_ID, notification)
    }

    private fun ByteArray.toHexString(): String =
        joinToString("") { "%02x".format(it) }
}
