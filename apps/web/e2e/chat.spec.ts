import { expect, test, type Page } from "@playwright/test";

const EMAIL = "marketer@lumi.test";
const PASSWORD = process.env.DEMO_MEMBER_PASSWORD ?? "marketer-demo-2026";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Mật khẩu").fill(PASSWORD);
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page).toHaveURL(/\/chat/);
}

test("sai mật khẩu → báo lỗi tại chỗ", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Mật khẩu").fill("sai-mat-khau");
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page.getByText("Sai email hoặc mật khẩu")).toBeVisible({ timeout: 10_000 });
});

test("login → hỏi giá → câu trả lời chính thức có citation hover được", async ({ page }) => {
  await login(page);
  await page.getByPlaceholder(/Hỏi về sản phẩm/).fill("How much is the Vitamin C Serum?");
  await page.keyboard.press("Enter");

  await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}/); // conversation mới
  await expect(page.getByText("Độ tin cậy:")).toBeVisible(); // message.completed → badge
  await expect(page.getByText("$42").first()).toBeVisible();

  const cite = page.locator("button", { hasText: /^1$/ }).first();
  await cite.hover();
  await expect(page.getByText(/hiệu lực/).first()).toBeVisible({ timeout: 10_000 });

  await expect(page.getByRole("button", { name: /Nguồn \(\d+\)/ })).toBeVisible();

  // Các bước agent: còn hiện sau khi xong, nhãn là KẾT QUẢ
  await expect(page.getByText(/^Tìm thấy \d+ đoạn từ \d+ tài liệu$/)).toBeVisible();
  await expect(page.getByText(/^Bằng chứng: /)).toBeVisible();
  await expect(page.getByText("Kiểm tra compliance & trích dẫn: đạt").or(page.getByText(/^Kiểm tra: \d+ vấn đề/)).first()).toBeVisible();

  // Mở output từng bước: truy vấn đã lập, các đoạn tìm được, bản nháp trước kiểm tra, kết quả kiểm tra
  await page.getByRole("button", { name: "Mở tất cả chi tiết" }).click();
  await expect(page.getByText("Câu hỏi độc lập (đã gộp ngữ cảnh)")).toBeVisible();
  await expect(page.getByText("Các đoạn tìm được (xếp theo độ liên quan)")).toBeVisible();
  await expect(page.getByText("Bản nháp (trước kiểm tra)")).toBeVisible();
  await expect(page.getByText("Độ tin cậy (tính theo luật, không hỏi LLM)")).toBeVisible();
  await page.screenshot({ path: "e2e/out/steps.png", fullPage: true });
  await page.getByRole("button", { name: "Thu gọn chi tiết" }).click();

  // Bấm [1] → panel mở chi tiết nguồn (đường dẫn, hiệu lực, toàn văn)
  await cite.click();
  await expect(page.locator("aside dd", { hasText: "products/vitamin-c-serum.md" })).toBeVisible();
  await expect(page.locator("aside dd", { hasText: "2026-03-01 · v2" })).toBeVisible();
  await page.screenshot({ path: "e2e/out/qa.png", fullPage: true });

  // F5 → lịch sử còn, sidebar có hội thoại
  await page.reload();
  await expect(page.getByText("$42").first()).toBeVisible();
  await expect(page.locator("aside a", { hasText: "How much is the Vitamin C Serum?" }).first()).toBeVisible();
  await expect(page.getByText(/^Tìm thấy \d+ đoạn từ \d+ tài liệu$/)).toBeVisible(); // bước đã lưu cùng message

  // 👍 lưu được
  await page.getByTitle("Hữu ích").first().click();
  await expect(page.getByText("Đã ghi nhận")).toBeVisible();
});

test("hỏi ship EU → không bịa, hiển thị phần còn thiếu", async ({ page }) => {
  await login(page);
  await page.getByPlaceholder(/Hỏi về sản phẩm/).fill("Do we ship to the EU and how long does it take?");
  await page.keyboard.press("Enter");
  // Kết quả cuối (không phải nhãn bước đang chạy): khối abstain hoặc badge "trả lời một phần"
  const final = page.getByText("Không đủ thông tin trong knowledge base").or(page.getByText("Trả lời một phần"));
  await expect(final.first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Dừng" })).toHaveCount(0);
  await page.screenshot({ path: "e2e/out/eu.png", fullPage: true });
});

test("quick action Creative brief → artifact panel, copy Markdown", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await login(page);
  await page.getByRole("button", { name: "Creative brief", exact: true }).click();
  await page.getByPlaceholder(/Creative brief cho/).fill("Creative brief for SPF 50 Daily Fluid on Instagram Reels");
  await page.keyboard.press("Enter");
  await expect(page.getByText("Xem ở panel bên phải →")).toBeVisible({ timeout: 170_000 });
  await page.getByRole("button", { name: "Artifact" }).click();
  await page.getByRole("button", { name: "Copy Markdown" }).click();
  const md = await page.evaluate(() => navigator.clipboard.readText());
  expect(md).toContain("Reapply every 2 hours");
  await page.screenshot({ path: "e2e/out/brief.png", fullPage: true });
});

test("F5 giữa lúc đang stream → stream tiếp tục tới kết quả", async ({ page }) => {
  await login(page);
  await page.getByPlaceholder(/Hỏi về sản phẩm/).fill("What is customers' #1 pain point?");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}/);
  await expect(page.getByRole("button", { name: "Dừng" })).toBeVisible(); // đang chạy
  await page.reload();
  await expect(page.getByText("Độ tin cậy:")).toBeVisible(); // active-job → replay SSE → message.completed
  await expect(page.locator("p", { hasText: "What is customers' #1 pain point?" })).toHaveCount(1);
});

test("bấm gửi 2 lần liên tiếp → chỉ 1 job", async ({ page }) => {
  await login(page);
  await page.getByPlaceholder(/Hỏi về sản phẩm/).fill("Is our serum FDA approved?");
  await page.getByTitle("Gửi (Enter)").dblclick();
  await expect(page.getByText("Độ tin cậy:").or(page.getByText("Không đủ thông tin"))).toBeVisible();
  await page.reload(); // lịch sử từ server: đúng 1 cặp user/assistant
  await expect(page.locator("p", { hasText: "Is our serum FDA approved?" })).toHaveCount(1);
  await expect(page.getByText(/FDA[- ]approved/i).first()).toBeVisible();
});
