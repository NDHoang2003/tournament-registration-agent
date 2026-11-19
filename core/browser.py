from pathlib import Path
from playwright.async_api import async_playwright

class BrowserSession:
    def __init__(self, user_data_dir, base_url, headless=False):
        self.user_data_dir, self.base_url, self.headless = str(Path(user_data_dir)), base_url, headless
    async def __aenter__(self):
        self.pw = await async_playwright().start()
        self.context = await self.pw.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir, headless=self.headless,
            viewport={"width": 1440, "height": 900},
            locale="vi-VN", timezone_id="Asia/Ho_Chi_Minh")
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        await self.page.goto(self.base_url, wait_until="domcontentloaded")
        return self
    async def ensure_login(self):
        print("Đăng nhập thủ công trong cửa sổ Chrome nếu cần.")
        input("Khi đã đăng nhập xong, nhấn Enter tại terminal để scan...")
    async def __aexit__(self, *args):
        await self.context.close()
        await self.pw.stop()
