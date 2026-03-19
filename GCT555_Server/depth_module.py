# depth_module.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np


@dataclass
class DepthConfig:
    # 공통
    smoothing_alpha: float = 0.20   # 0~1, 클수록 최신값 반영 강함
    clamp_min: float = -20.0
    clamp_max: float = 20.0

    # Face 전용
    face_global_scale: float = 4.0      # tz 스케일
    face_local_scale: float = 0.05      # landmark z의 상대 오프셋 스케일
    face_invert_tz: bool = False        # 환경 따라 True 필요 가능
    face_invert_local_z: bool = False   # 환경 따라 True 필요 가능

    # Pose / Hand 전용
    pose_invert_world_z: bool = False
    hand_invert_world_z: bool = False

    # 서버에서 디버그로 raw도 같이 보낼지
    include_debug_raw: bool = True


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class DepthState:
    """
    서버 프로세스 내부에서 프레임 간 smoothing을 유지.
    pose/face는 single target, hand는 multi-hand를 고려해 index 기반으로 저장.
    """
    def __init__(self, cfg: Optional[DepthConfig] = None):
        self.cfg = cfg or DepthConfig()
        self._face_global_z: Dict[int, float] = {}
        self._pose_global_z: Dict[int, float] = {}
        self._hand_global_z: Dict[int, float] = {}

    def _smooth(self, cache: Dict[int, float], key: int, value: float) -> float:
        prev = cache.get(key, value)
        a = self.cfg.smoothing_alpha
        smoothed = (1.0 - a) * prev + a * value
        cache[key] = smoothed
        return smoothed


def _parse_4x4_matrix(matrix_like: Any) -> Optional[np.ndarray]:
    try:
        M = np.array(matrix_like, dtype=np.float32)
        if M.size != 16:
            return None
        M = M.reshape(4, 4)
        return M
    except Exception:
        return None


def _mean_z_from_world_landmarks(world_landmarks: Sequence[Any]) -> Optional[float]:
    if not world_landmarks:
        return None
    zs = []
    for lm in world_landmarks:
        z = getattr(lm, "z", None)
        if z is None:
            continue
        zs.append(float(z))
    if not zs:
        return None
    return float(np.mean(zs))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_landmark_dict(lm: Any) -> Dict[str, float]:
    return {
        "x": _safe_float(getattr(lm, "x", 0.0), 0.0),
        "y": _safe_float(getattr(lm, "y", 0.0), 0.0),
        "z": _safe_float(getattr(lm, "z", 0.0), 0.0),
        "visibility": _safe_float(getattr(lm, "visibility", None), 1.0),
    }


def build_pose_payload(
    result: Any,
    depth_state: DepthState,
    pose_index: int = 0,
) -> Optional[Dict[str, Any]]:
    """
    반환 형식:
    {
      "landmarks": [...],
      "world_landmarks": [...],
      "depth": {
        "mode": "pose_world",
        "global_z": ...,
        "per_landmark_z": [...]
      }
    }
    """
    if not result or not getattr(result, "pose_landmarks", None):
        return None

    pose_landmarks = result.pose_landmarks[pose_index]
    world_landmarks = []
    if getattr(result, "pose_world_landmarks", None):
        if pose_index < len(result.pose_world_landmarks):
            world_landmarks = result.pose_world_landmarks[pose_index]

    lm_list = [_safe_landmark_dict(lm) for lm in pose_landmarks]
    world_list = [_safe_landmark_dict(lm) for lm in world_landmarks]

    global_z = _mean_z_from_world_landmarks(world_landmarks)
    if global_z is None:
        global_z = 0.0

    if depth_state.cfg.pose_invert_world_z:
        global_z = -global_z

    global_z = _clamp(global_z, depth_state.cfg.clamp_min, depth_state.cfg.clamp_max)
    global_z = depth_state._smooth(depth_state._pose_global_z, pose_index, global_z)

    per_landmark_z = []
    if world_landmarks:
        for lm in world_landmarks:
            z = float(getattr(lm, "z", 0.0))
            if depth_state.cfg.pose_invert_world_z:
                z = -z
            per_landmark_z.append(_clamp(z, depth_state.cfg.clamp_min, depth_state.cfg.clamp_max))
    else:
        # fallback: normalized z
        for lm in pose_landmarks:
            per_landmark_z.append(float(getattr(lm, "z", 0.0)))

    payload = {
        "landmarks": lm_list,
        "world_landmarks": world_list,
        "depth": {
            "mode": "pose_world",
            "global_z": global_z,
            "per_landmark_z": per_landmark_z,
        }
    }
    return payload


def build_hand_payloads(
    result: Any,
    depth_state: DepthState,
) -> List[Dict[str, Any]]:
    """
    반환 형식:
    [
      {
        "handedness": "...",
        "landmarks": [...],
        "world_landmarks": [...],
        "depth": {
          "mode": "hand_world",
          "global_z": ...,
          "per_landmark_z": [...]
        }
      },
      ...
    ]
    """
    if not result or not getattr(result, "hand_landmarks", None):
        return []

    outputs: List[Dict[str, Any]] = []
    hand_world_landmarks = getattr(result, "hand_world_landmarks", None)
    handedness = getattr(result, "handedness", None)

    for idx, hand_landmarks in enumerate(result.hand_landmarks):
        world_landmarks = []
        if hand_world_landmarks and idx < len(hand_world_landmarks):
            world_landmarks = hand_world_landmarks[idx]

        label = "Unknown"
        if handedness and idx < len(handedness) and len(handedness[idx]) > 0:
            label = handedness[idx][0].category_name

        lm_list = [_safe_landmark_dict(lm) for lm in hand_landmarks]
        world_list = [_safe_landmark_dict(lm) for lm in world_landmarks]

        global_z = _mean_z_from_world_landmarks(world_landmarks)
        if global_z is None:
            global_z = 0.0

        if depth_state.cfg.hand_invert_world_z:
            global_z = -global_z

        global_z = _clamp(global_z, depth_state.cfg.clamp_min, depth_state.cfg.clamp_max)
        global_z = depth_state._smooth(depth_state._hand_global_z, idx, global_z)

        per_landmark_z = []
        if world_landmarks:
            for lm in world_landmarks:
                z = float(getattr(lm, "z", 0.0))
                if depth_state.cfg.hand_invert_world_z:
                    z = -z
                per_landmark_z.append(_clamp(z, depth_state.cfg.clamp_min, depth_state.cfg.clamp_max))
        else:
            for lm in hand_landmarks:
                per_landmark_z.append(float(getattr(lm, "z", 0.0)))

        outputs.append({
            "handedness": label,
            "landmarks": lm_list,
            "world_landmarks": world_list,
            "depth": {
                "mode": "hand_world",
                "global_z": global_z,
                "per_landmark_z": per_landmark_z,
            }
        })

    return outputs


def build_face_payloads(
    result: Any,
    depth_state: DepthState,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, float]]]:
    """
    Face는 공식적으로 3D landmarks + facial transformation matrix를 제공한다.
    여기서는:
      - global_z = matrix tz
      - per_landmark_z = global_z + (landmark z * local_scale)
    로 보낸다.

    반환:
      faces_data, raw_pose_debug
    """
    if not result or not getattr(result, "face_landmarks", None):
        return [], []

    matrices = getattr(result, "facial_transformation_matrixes", None)
    outputs: List[Dict[str, Any]] = []
    raw_pose_debug: List[Dict[str, float]] = []

    for i, face_landmarks in enumerate(result.face_landmarks):
        lm_list = [_safe_landmark_dict(lm) for lm in face_landmarks]

        raw_tx = raw_ty = raw_tz = 0.0
        has_pose = False

        if matrices is not None and i < len(matrices) and matrices[i] is not None:
            M = _parse_4x4_matrix(matrices[i])
            if M is not None:
                raw_tx = float(M[0, 3])
                raw_ty = float(M[1, 3])
                raw_tz = float(M[2, 3])
                has_pose = True

        global_z = raw_tz
        if depth_state.cfg.face_invert_tz:
            global_z = -global_z
        global_z *= depth_state.cfg.face_global_scale
        global_z = _clamp(global_z, depth_state.cfg.clamp_min, depth_state.cfg.clamp_max)
        global_z = depth_state._smooth(depth_state._face_global_z, i, global_z)

        per_landmark_z = []
        for lm in face_landmarks:
            local_z = float(getattr(lm, "z", 0.0))
            if depth_state.cfg.face_invert_local_z:
                local_z = -local_z
            z = global_z + (local_z * depth_state.cfg.face_local_scale)
            z = _clamp(z, depth_state.cfg.clamp_min, depth_state.cfg.clamp_max)
            per_landmark_z.append(z)

        face_item: Dict[str, Any] = {
            "landmarks": lm_list,
            "depth": {
                "mode": "face_transform_plus_local",
                "global_z": global_z,
                "per_landmark_z": per_landmark_z,
            }
        }

        if has_pose:
            face_item["face_pose"] = {
                "tx": raw_tx,
                "ty": raw_ty,
                "tz": raw_tz
            }
            raw_pose_debug.append({
                "tx": raw_tx,
                "ty": raw_ty,
                "tz": raw_tz
            })
        else:
            face_item["face_pose"] = None

        outputs.append(face_item)

    return outputs, raw_pose_debug