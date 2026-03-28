import cv2
import sys
import time

def main():
    # 카메라 인덱스 0, 1, 2 순서로 시도
    cap = None
    for index in [0, 1, 2]:
        print(f"Trying camera index {index}...")
        cap = cv2.VideoCapture(index)
        time.sleep(2)  # 워밍업 시간
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"Camera index {index} works!")
            break
        cap.release()
        cap = None

    if cap is None:
        print("Error: No working camera found.")
        sys.exit(1)

    print("Webcam connected! Press 'q' to quit")

    while True:
        ret, frame = cap.read()

        if not ret or frame is None:
            print("Frame read failed, retrying...")
            time.sleep(0.1)
            continue

        cv2.imshow("Webcam Feed", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()