import easyocr
import cv2
import re

class PlateOCR:
    def __init__(self, languages=['en']):
        # Initialize EasyOCR reader (will download models on first run)
        self.reader = easyocr.Reader(languages)
        
    def preprocess_for_ocr(self, img):
        if img is None or img.size == 0:
            return None
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Apply thresholding
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return thresh

    def read_plate(self, cropped_img):
        processed = self.preprocess_for_ocr(cropped_img)
        if processed is None:
            return ""
        
        # Read text (detail=0 returns plain text list, faster than full coordinate mode)
        results = self.reader.readtext(processed, detail=0)
        
        # Join all detected text pieces
        raw_text = "".join(results).upper().replace(" ", "")
        
        # Simple cleanup (allow A-Z and 0-9)
        clean_text = re.sub(r'[^A-Z0-9]', '', raw_text)
        
        return clean_text

if __name__ == "__main__":
    ocr = PlateOCR()
    img = cv2.imread('test_plate.jpg')
    if img is not None:
        print(f"Plate number: {ocr.read_plate(img)}")
    else:
        print("Test image not found.")
