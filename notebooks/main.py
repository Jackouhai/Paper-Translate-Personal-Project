from pathlib import Path
import os
from paddleocr import PaddleOCRVL

# PDF file path
pdf_input = "/home/bocchi/Downloads/DeepSeekOCR.pdf"
pdf_path = Path(pdf_input)

output_folder = Path("output") / pdf_path.stem

output_folder.mkdir(parents=True, exist_ok=True)



pipeline = PaddleOCRVL(vl_rec_backend="vllm-server", vl_rec_server_url="http://127.0.0.1:8000/v1")
output = pipeline.predict(str(pdf_path))
for i, res in enumerate(output):
    print(f"--> Saving page {i+1}")
    try:
        res.save_to_json(save_path=str(output_folder))
        res.save_to_markdown(save_path=str(output_folder))
    except Exception as e:
        print(f"Lỗi lưu trang {i+1}: {e}")
        
print(f"File sẽ được lưu vào: {output_folder}")