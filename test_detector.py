import cv2
from detection import PlateDetector
import config

def test_webcam():
    print(f"Loading model from: {config.MODEL_PATH}")
    detector = PlateDetector(config.MODEL_PATH, config.CONF_THRESHOLD)
    
    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    print("Webcam started. Press 'q' to quit.")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        results = detector.detect(frame)
        
        for res in results:
            x1, y1, x2, y2 = res['box']
            conf = res['confidence']
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"Plate: {conf:.2f}", (x1, y1 - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Show crop in a separate window
            cv2.imshow("Crop", res['crop'])
            
        cv2.imshow("Test Detector", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    test_webcam()
