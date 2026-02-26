package com.neuralai.agent.core.skills.location

import android.annotation.SuppressLint
import android.content.Context
import android.location.Location
import com.google.android.gms.location.LocationServices
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.tasks.await
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class LocationSkill @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val fusedClient = LocationServices.getFusedLocationProviderClient(context)

    /**
     * Gets the last known GPS location. Returns null if unavailable.
     * Requires ACCESS_FINE_LOCATION permission to be granted at runtime.
     */
    @SuppressLint("MissingPermission")
    suspend fun getCurrentLocation(): Location? {
        return try {
            fusedClient.lastLocation.await()
        } catch (e: Exception) {
            null
        }
    }

    /**
     * Returns a human-readable string of the current location.
     */
    @SuppressLint("MissingPermission")
    suspend fun getLocationString(): String {
        val location = getCurrentLocation()
        return if (location != null) {
            "Latitude: ${location.latitude}, Longitude: ${location.longitude} (Accuracy: ${location.accuracy}m)"
        } else {
            "Location unavailable. Ensure GPS is enabled and permissions are granted."
        }
    }
}
