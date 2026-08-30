import os
import sys

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.utils.ocr_processor import OCRProcessor

def test_ocr():
    ocr_processor = OCRProcessor()
    
    # 测试OCR初始化
    print("OCR Processor initialized successfully!")
    
    # 获取test目录的路径
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 支持的图片格式
    image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp']
    
    # 查找test目录下的所有图片文件
    image_files = []
    for filename in os.listdir(test_dir):
        if os.path.splitext(filename)[1].lower() in image_extensions:
            image_files.append(filename)
    
    if not image_files:
        print("没有找到测试图片！请将图片文件放到test目录下。")
        print("支持的图片格式：", ', '.join(image_extensions))
        return
    
    print(f"找到 {len(image_files)} 个测试图片：")
    for image_file in image_files:
        print(f"  - {image_file}")
    
    print("\n开始OCR测试...")
    print("=" * 60)
    
    # 对每个图片进行OCR测试
    for image_file in image_files:
        image_path = os.path.join(test_dir, image_file)
        print(f"\n处理图片：{image_file}")
        print(f"路径：{image_path}")
        
        try:
            # 提取文本
            ocr_text = ocr_processor.extract_text(image_path)
            
            if ocr_text.strip():
                print("OCR识别结果：")
                print("-" * 60)
                print(ocr_text)
                print("-" * 60)
            else:
                print("OCR识别结果：未识别到文本")
                
        except Exception as e:
            print(f"OCR处理错误：{e}")
    
    print("\n" + "=" * 60)
    print("OCR测试完成！")

if __name__ == "__main__":
    test_ocr()