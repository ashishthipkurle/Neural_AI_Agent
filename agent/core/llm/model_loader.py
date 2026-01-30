"""
Model Loader - GGUF model management.

This module handles:
- Model discovery
- Model loading/unloading
- Memory optimization
- Model metadata
"""
import logging
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModelInfo:
    """Information about a loaded or available model."""
    name: str
    path: str
    size_bytes: int
    format: str  # gguf, onnx, etc.
    quantization: Optional[str] = None
    context_length: int = 4096
    is_loaded: bool = False
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def size_gb(self) -> float:
        return self.size_bytes / (1024 ** 3)


class ModelLoader:
    """
    Manages GGUF model loading and lifecycle.
    
    Features:
    - Automatic model discovery
    - Memory-efficient loading
    - Model switching
    - Metadata extraction
    """
    
    SUPPORTED_EXTENSIONS = frozenset({'.gguf', '.ggml'})
    
    def __init__(self, models_dir: str = "models"):
        """
        Initialize the Model Loader.
        
        Args:
            models_dir: Directory to scan for models.
        """
        self.logger = logging.getLogger("ModelLoader")
        self.models_dir = Path(models_dir)
        self._available_models: Dict[str, ModelInfo] = {}
        self._loaded_model: Optional[Any] = None
        self._loaded_model_name: Optional[str] = None
        
        # Ensure models directory exists
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Scan for available models
        self._scan_models()
        
        self.logger.info(f"ModelLoader initialized. Found {len(self._available_models)} models.")
    
    def _scan_models(self) -> None:
        """Scan models directory for available models."""
        self._available_models.clear()
        
        if not self.models_dir.exists():
            self.logger.warning(f"Models directory does not exist: {self.models_dir}")
            return
        
        for file_path in self.models_dir.rglob("*"):
            if file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                model_name = file_path.stem
                try:
                    model_info = ModelInfo(
                        name=model_name,
                        path=str(file_path.absolute()),
                        size_bytes=file_path.stat().st_size,
                        format=file_path.suffix[1:],  # Remove leading dot
                        quantization=self._detect_quantization(model_name)
                    )
                    self._available_models[model_name] = model_info
                    self.logger.debug(f"Found model: {model_name} ({model_info.size_gb:.2f} GB)")
                except Exception as e:
                    self.logger.warning(f"Failed to scan model {file_path}: {e}")
    
    def _detect_quantization(self, model_name: str) -> Optional[str]:
        """Detect quantization from model name."""
        quant_patterns = ['q2', 'q3', 'q4', 'q5', 'q6', 'q8', 'f16', 'f32']
        model_lower = model_name.lower()
        
        for pattern in quant_patterns:
            if pattern in model_lower:
                return pattern.upper()
        
        return None
    
    def list_models(self) -> List[ModelInfo]:
        """List all available models."""
        return list(self._available_models.values())
    
    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """Get information about a specific model."""
        return self._available_models.get(model_name)
    
    def load_model(
        self,
        model_name: str,
        n_ctx: int = 4096,
        n_gpu_layers: int = -1
    ) -> bool:
        """
        Load a model into memory.
        
        Args:
            model_name: Name of the model to load.
            n_ctx: Context window size.
            n_gpu_layers: Number of layers to offload to GPU.
        
        Returns:
            True if successful, False otherwise.
        """
        if model_name not in self._available_models:
            self.logger.error(f"Model not found: {model_name}")
            return False
        
        # Unload current model if any
        if self._loaded_model:
            self.unload_model()
        
        model_info = self._available_models[model_name]
        
        try:
            from llama_cpp import Llama
            
            self.logger.info(f"Loading model: {model_name} ({model_info.size_gb:.2f} GB)")
            
            self._loaded_model = Llama(
                model_path=model_info.path,
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                verbose=False
            )
            
            self._loaded_model_name = model_name
            model_info.is_loaded = True
            model_info.context_length = n_ctx
            
            self.logger.info(f"Model loaded successfully: {model_name}")
            return True
            
        except ImportError:
            self.logger.error("llama-cpp-python not installed")
            return False
        except Exception as e:
            self.logger.error(f"Failed to load model {model_name}: {e}")
            return False
    
    def unload_model(self) -> None:
        """Unload the currently loaded model."""
        if self._loaded_model:
            self.logger.info(f"Unloading model: {self._loaded_model_name}")
            
            # Mark as unloaded
            if self._loaded_model_name in self._available_models:
                self._available_models[self._loaded_model_name].is_loaded = False
            
            # Delete reference to free memory
            del self._loaded_model
            self._loaded_model = None
            self._loaded_model_name = None
            
            # Force garbage collection
            import gc
            gc.collect()
    
    def get_loaded_model(self) -> Optional[Any]:
        """Get the currently loaded model instance."""
        return self._loaded_model
    
    def is_model_loaded(self) -> bool:
        """Check if a model is currently loaded."""
        return self._loaded_model is not None
    
    def refresh(self) -> int:
        """
        Refresh the list of available models.
        
        Returns:
            Number of models found.
        """
        self._scan_models()
        return len(self._available_models)
    
    def download_model(self, model_url: str, model_name: str) -> bool:
        """
        Download a model from URL.
        
        NOTE: This violates the "NO internet access" constraint.
        This method is provided for initial setup only and should
        be disabled in production.
        
        Args:
            model_url: URL to download from.
            model_name: Name to save the model as.
        
        Returns:
            True if successful, False otherwise.
        """
        self.logger.warning("Model download is disabled for security compliance.")
        self.logger.info("Please download models manually and place in the models directory.")
        return False
