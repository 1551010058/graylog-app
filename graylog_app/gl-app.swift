// Graylog.app — cửa sổ native bọc trang quản lý của gl (gl-ui.py).
// Build: xem ~/.local/bin/gl-app-build
import Cocoa
import WebKit
import UserNotifications

final class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate, UNUserNotificationCenterDelegate {
    let bin = NSHomeDirectory() + "/.local/bin"
    var server: Process?
    var url: URL?
    var windows: [NSWindow] = []

    // Server là tiến trình con: tắt app (đóng stdin của nó) là server tự thoát.
    func startServer() -> Bool {
        let p = Process(), out = Pipe()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        p.arguments = [bin + "/gl-ui.py", bin + "/gl", "app"]
        p.standardInput = Pipe(); p.standardOutput = out; p.standardError = FileHandle.nullDevice
        guard (try? p.run()) != nil else { return false }
        server = p
        var line = Data()
        while let b = Optional(out.fileHandleForReading.readData(ofLength: 1)), !b.isEmpty, b[0] != 10 { line += b }
        url = URL(string: String(decoding: line, as: UTF8.self))
        return url != nil
    }

    @objc func newWindow(_ sender: Any?) {
        if server?.isRunning != true { _ = startServer() }
        guard let url = url else { return }
        let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 900, height: 720),
                         styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        w.title = "Graylog"; w.isReleasedWhenClosed = false
        w.setFrameAutosaveName("main")
        if let last = windows.last(where: { $0.isVisible }) {   // cửa sổ mới lệch một chút so với cửa sổ trước
            w.setFrameTopLeftPoint(NSPoint(x: last.frame.minX + 28, y: last.frame.maxY - 28))
        } else if !w.setFrameUsingName("main") { w.center() }
        let web = WKWebView(frame: .zero)
        web.uiDelegate = self
        web.load(URLRequest(url: url))
        w.contentView = web
        windows = windows.filter { $0.isVisible } + [w]
        w.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationDidFinishLaunching(_ n: Notification) {
        let main = NSMenu()
        func menu(_ title: String, _ items: [(String, Selector, String)]) {
            let m = NSMenu(title: title)
            for (t, s, k) in items { m.addItem(withTitle: t, action: s, keyEquivalent: k) }
            let i = NSMenuItem(); i.submenu = m; main.addItem(i)
        }
        menu("Graylog", [("Settings…", #selector(openSettings(_:)), ","),
                         ("Hide Graylog", #selector(NSApplication.hide(_:)), "h"),
                         ("Quit Graylog", #selector(NSApplication.terminate(_:)), "q")])
        menu("File", [("New Window", #selector(newWindow(_:)), "n"),
                      ("Close Window", #selector(NSWindow.performClose(_:)), "w")])
        menu("Edit", [("Undo", Selector(("undo:")), "z"), ("Cut", #selector(NSText.cut(_:)), "x"),
                      ("Copy", #selector(NSText.copy(_:)), "c"), ("Paste", #selector(NSText.paste(_:)), "v"),
                      ("Select All", #selector(NSText.selectAll(_:)), "a")])
        menu("View", [("Reload", #selector(WKWebView.reload(_:)), "r"),
                      ("Back", #selector(WKWebView.goBack(_:)), "["), ("Forward", #selector(WKWebView.goForward(_:)), "]")])
        NSApp.mainMenu = main
        UNUserNotificationCenter.current().delegate = self
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, _ in }
        Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { _ in self.checkAnswers() }
        guard startServer() else {
            let a = NSAlert(); a.messageText = "Không khởi động được gl-ui.py"; a.runModal(); NSApp.terminate(nil); return
        }
        checkAnswers()   // áp giao diện Sáng/Tối đã lưu trước khi mở cửa sổ
        newWindow(nil)
    }

    @objc func openSettings(_ sender: Any?) {   // mở hộp cài đặt của trang (nút bánh răng)
        if !(NSApp.keyWindow?.contentView is WKWebView) { newWindow(nil) }
        (NSApp.keyWindow?.contentView as? WKWebView)?.evaluateJavaScript("document.getElementById('cfg')?.click()")
    }

    // Bấm icon trên Dock: quay lại cửa sổ đang có; chỉ tạo mới khi đã đóng hết.
    func applicationShouldHandleReopen(_ s: NSApplication, hasVisibleWindows: Bool) -> Bool {
        if !hasVisibleWindows { newWindow(nil) }
        return true
    }
    func applicationDockMenu(_ s: NSApplication) -> NSMenu? {
        let m = NSMenu(); m.addItem(withTitle: "New Window", action: #selector(newWindow(_:)), keyEquivalent: ""); return m
    }
    func applicationWillTerminate(_ n: Notification) { server?.terminate() }

    // AI chạy ngầm ghi mỗi câu trả lời ra ~/.config/gl/ask/<stamp>.html. Có file mới: hiện thông báo mang tên và icon của app.
    // (Không để trang web tự báo: WKWebView hãm timer của cửa sổ bị che nên trang không biết AI đã xong.)
    // đang ở trong app cũng hiện thông báo (mặc định macOS giấu thông báo của app đang đứng trước)
    func userNotificationCenter(_ c: UNUserNotificationCenter, willPresent n: UNNotification,
                                withCompletionHandler done: @escaping (UNNotificationPresentationOptions) -> Void) { done([.banner, .sound]) }
    var seen: Set<String>?
    func checkAnswers() {
        let th = ((try? String(contentsOfFile: NSHomeDirectory() + "/.config/gl/theme", encoding: .utf8)) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let ap = th == "dark" ? NSAppearance(named: .darkAqua) : th == "light" ? NSAppearance(named: .aqua) : nil
        if NSApp.appearance?.name != ap?.name { NSApp.appearance = ap }
        let dir = NSHomeDirectory() + "/.config/gl/ask"
        let all = (try? FileManager.default.contentsOfDirectory(atPath: dir)) ?? []
        func note(_ id: String, _ title: String, _ body: String) {
            let n = UNMutableNotificationContent(); n.sound = .default; n.title = title; n.body = String(body.prefix(140))
            UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: id, content: n, trigger: nil))
        }
        for f in all where f.hasSuffix(".note") {   // kết quả "Lưu và kiểm tra" ở Cài đặt AI, do gl-ui.py ghi
            let t = (try? String(contentsOfFile: dir + "/" + f, encoding: .utf8)) ?? ""
            try? FileManager.default.removeItem(atPath: dir + "/" + f)
            note(f, "Kiểm tra AI xong", t)
        }
        let now = Set(all.filter { $0.hasSuffix(".html") })
        defer { seen = now }
        guard let old = seen else { return }
        for f in now.subtracting(old) {
            let raw = (try? String(contentsOfFile: dir + "/" + f, encoding: .utf8)) ?? ""
            var text = raw.replacingOccurrences(of: "<[^>]+>", with: " ", options: .regularExpression)
            for (k, v) in [("&lt;", "<"), ("&gt;", ">"), ("&quot;", "\""), ("&#x27;", "'"), ("&amp;", "&")] { text = text.replacingOccurrences(of: k, with: v) }
            text = text.replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression).trimmingCharacters(in: .whitespaces)
            note(f, raw.contains("<!--fail-->") ? "AI không trả lời được" : "AI đã trả lời xong", text)
        }
    }

    // confirm()/alert() của trang (vd: hỏi lại khi Xoá)
    func webView(_ v: WKWebView, runJavaScriptConfirmPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo,
                 completionHandler done: @escaping (Bool) -> Void) {
        let a = NSAlert(); a.messageText = m; a.addButton(withTitle: "OK"); a.addButton(withTitle: "Huỷ")
        done(a.runModal() == .alertFirstButtonReturn)
    }
    func webView(_ v: WKWebView, runJavaScriptAlertPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo,
                 completionHandler done: @escaping () -> Void) {
        let a = NSAlert(); a.messageText = m; a.runModal(); done()
    }
    // <input type=file> (nút 📎 ở khung chat AI): WKWebView không tự mở hộp chọn file
    func webView(_ v: WKWebView, runOpenPanelWith p: WKOpenPanelParameters, initiatedByFrame f: WKFrameInfo,
                 completionHandler done: @escaping ([URL]?) -> Void) {
        let o = NSOpenPanel(); o.allowsMultipleSelection = p.allowsMultipleSelection
        done(o.runModal() == .OK ? o.urls : nil)
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
