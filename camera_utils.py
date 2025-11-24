# camera_utils.py
import cv2

def initialize_camera(prefer_droidcam=True):
    """
    Attempts to open DroidCam (Index 1). 
    If fails, falls back to Laptop Webcam (Index 0).
    
    Returns:
        cap: The OpenCV video capture object
        source_name: String ('DroidCam' or 'Webcam')
        warning_message: Message if fallback occurred, else None
    """
    # 1. Try Phone First (Index 1)
    if prefer_droidcam:
        print("[CAMERA] Attempting to connect to DroidCam (Index 1)...")
        # DroidCam usually mounts as Index 1. 
        # If using IP Webcam (URL), change 1 to "http://192.168.x.x:8080/video"
        cap = cv2.VideoCapture(1) 
        
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                print("[CAMERA] Success: Connected to DroidCam.")
                return cap, "DroidCam (Phone)", None
            else:
                cap.release()
    
    # 2. Fallback to Webcam (Index 0)
    print("[CAMERA] Falling back to Laptop Webcam (Index 0)...")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        return None, "None", "CRITICAL: No Camera Found!"
    
    # If we wanted DroidCam but got Webcam, return a warning
    warning = "Phone Not Detected - Using Webcam" if prefer_droidcam else None
    
    return cap, "Laptop Webcam", warning