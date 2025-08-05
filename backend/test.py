import unittest
import json
from app import app  # 假设 Flask 应用在 app.py 中

class FlaskTestCase(unittest.TestCase):

    # 设置 Flask 测试客户端
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    # 测试 generate-ply 接口
    def test_generate_ply(self):
        # 创建一个 JSON 请求体
        data = {
            'min_val': 1500,
            'max_val': 1501.1
        }

        # 发送 POST 请求
        response = self.app.post('/generate-ply', data=json.dumps(data), content_type='application/json')

        # 验证响应状态码是否为 200
        self.assertEqual(response.status_code, 200)

        # 验证响应的文件类型是否为 application/octet-stream
        self.assertEqual(response.content_type, 'application/octet-stream')

        # 可以进一步检查文件内容（如果需要的话）

if __name__ == '__main__':
    unittest.main()
