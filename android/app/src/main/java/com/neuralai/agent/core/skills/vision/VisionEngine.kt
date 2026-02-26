package com.neuralai.agent.core.skills.vision

import android.graphics.Bitmap
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.Face
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import com.google.mlkit.vision.objects.DetectedObject
import com.google.mlkit.vision.objects.ObjectDetection
import com.google.mlkit.vision.objects.defaults.ObjectDetectorOptions
import com.google.mlkit.vision.text.Text
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlinx.coroutines.tasks.await
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class VisionEngine @Inject constructor() {

    // 1. Face Detector
    // Configured for high accuracy, finding all landmarks (eyes, ears, cheeks) and classifications (smiling, eyes open)
    private val faceDetector = FaceDetection.getClient(
        FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_ACCURATE)
            .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_ALL)
            .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_ALL)
            .build()
    )

    // 2. Object Detector
    // Configured to find multiple objects in a single image and return their conceptual labels (e.g. "Laptop", "Coffee cup")
    private val objectDetector = ObjectDetection.getClient(
        ObjectDetectorOptions.Builder()
            .setDetectorMode(ObjectDetectorOptions.SINGLE_IMAGE_MODE)
            .enableMultipleObjects()
            .enableClassification()
            .build()
    )

    // 3. Text Recognizer (OCR)
    // Configured for standard Latin script text reading
    private val textRecognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)

    /**
     * Analyzes a bitmap for human faces.
     */
    suspend fun analyzeFaces(bitmap: Bitmap): List<Face> {
        return try {
            val image = InputImage.fromBitmap(bitmap, 0)
            faceDetector.process(image).await()
        } catch (e: Exception) {
            emptyList()
        }
    }

    /**
     * Analyzes a bitmap for common physical objects.
     */
    suspend fun analyzeObjects(bitmap: Bitmap): List<DetectedObject> {
        return try {
            val image = InputImage.fromBitmap(bitmap, 0)
            objectDetector.process(image).await()
        } catch (e: Exception) {
            emptyList()
        }
    }

    /**
     * Extracts text from a bitmap (OCR).
     */
    suspend fun readText(bitmap: Bitmap): Text? {
        return try {
            val image = InputImage.fromBitmap(bitmap, 0)
            textRecognizer.process(image).await()
        } catch (e: Exception) {
            null
        }
    }
}
