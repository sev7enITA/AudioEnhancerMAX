"""
AudioEnhancerMAX by Fd - Noise Removal Service
Combines DeepFilterNet (deep learning) + noisereduce (spectral gating).
"""
import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Lazy-loaded models
_df_model = None
_df_state = None


def _init_deepfilter():
    """Lazily initialize DeepFilterNet model."""
    global _df_model, _df_state
    if _df_model is None:
        try:
            from df.enhance import init_df
            _df_model, _df_state, _ = init_df()
            logger.info("DeepFilterNet model loaded successfully")
        except ImportError:
            logger.warning("DeepFilterNet not installed. Using noisereduce fallback.")
        except Exception as e:
            logger.warning(f"DeepFilterNet init failed: {e}. Using noisereduce fallback.")


def remove_noise_deepfilter(
    audio: np.ndarray,
    sr: int,
    strength: float = 0.7
) -> np.ndarray:
    """
    Remove noise using DeepFilterNet.
    Best for: general background noise while preserving speech clarity.
    """
    _init_deepfilter()

    if _df_model is not None and _df_state is not None:
        try:
            import torch
            from df.enhance import enhance

            # DeepFilterNet expects 48kHz
            target_sr = _df_state.sr()
            if sr != target_sr:
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)

            # Convert to tensor
            audio_tensor = torch.from_numpy(audio).unsqueeze(0).float()

            # Enhance
            enhanced = enhance(_df_model, _df_state, audio_tensor)

            # Convert back
            enhanced_np = enhanced.squeeze().numpy()

            # Blend with original based on strength
            if strength < 1.0:
                enhanced_np = audio * (1 - strength) + enhanced_np * strength

            # Resample back if needed
            if sr != target_sr:
                enhanced_np = librosa.resample(enhanced_np, orig_sr=target_sr, target_sr=sr)

            return enhanced_np

        except Exception as e:
            logger.error(f"DeepFilterNet processing failed: {e}")
            return remove_noise_spectral(audio, sr, strength)
    else:
        return remove_noise_spectral(audio, sr, strength)


def remove_noise_spectral(
    audio: np.ndarray,
    sr: int,
    strength: float = 0.7,
    noise_clip: Optional[np.ndarray] = None
) -> np.ndarray:
    """
    Remove noise using noisereduce (spectral gating).
    v2.0: Added temporal/frequency smoothing + wet/dry mix to prevent
    metallic "musical noise" artifacts.
    """
    try:
        import noisereduce as nr

        # v2.0: Cap prop_decrease at 0.85 - never remove more than 85%
        # of noise to preserve natural room tone and avoid artifacts.
        # (v1 used strength * 1.2 which could exceed 1.0 = metallic sound)
        prop_decrease = min(0.85, strength * 0.85)

        # v2.0: Raise n_std_thresh minimum to 1.5 (v1 went down to 1.0)
        # Lower values = more aggressive gating = more artifacts
        n_std_thresh = max(1.5, 2.0 - (strength * 0.5))

        reduced = nr.reduce_noise(
            y=audio,
            sr=sr,
            y_noise=noise_clip,
            prop_decrease=prop_decrease,
            stationary=noise_clip is None,
            n_std_thresh_stationary=n_std_thresh,
            # v2.0: Smoothing to prevent metallic flutter
            time_mask_smooth_ms=100,
            freq_mask_smooth_hz=500,
        )

        # v2.0: Wet/dry mix - blend processed with original to preserve
        # natural character. Higher strength = more processed signal.
        wet = min(0.85, strength)
        dry = 1.0 - wet
        result = reduced * wet + audio * dry

        return result

    except ImportError:
        logger.error("noisereduce not installed")
        return audio
    except Exception as e:
        logger.error(f"Spectral noise reduction failed: {e}")
        return audio


def remove_noise(
    audio: np.ndarray,
    sr: int,
    strength: float = 0.7,
    use_deep_learning: bool = True
) -> np.ndarray:
    """
    Main noise removal function.
    Tries DeepFilterNet first, falls back to spectral gating.
    """
    if use_deep_learning:
        return remove_noise_deepfilter(audio, sr, strength)
    else:
        return remove_noise_spectral(audio, sr, strength)
