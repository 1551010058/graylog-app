// Graylog.app — cửa sổ native bọc trang quản lý của gl (gl-ui.py).
// Build: xem ~/.local/bin/gl-app-build
import Cocoa
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate {
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
        menu("Graylog", [("Hide Graylog", #selector(NSApplication.hide(_:)), "h"),
                         ("Quit Graylog", #selector(NSApplication.terminate(_:)), "q")])
        menu("File", [("New Window", #selector(newWindow(_:)), "n"),
                      ("Close Window", #selector(NSWindow.performClose(_:)), "w")])
        menu("Edit", [("Undo", Selector(("undo:")), "z"), ("Cut", #selector(NSText.cut(_:)), "x"),
                      ("Copy", #selector(NSText.copy(_:)), "c"), ("Paste", #selector(NSText.paste(_:)), "v"),
                      ("Select All", #selector(NSText.selectAll(_:)), "a")])
        menu("View", [("Reload", #selector(WKWebView.reload(_:)), "r"),
                      ("Back", #selector(WKWebView.goBack(_:)), "["), ("Forward", #selector(WKWebView.goForward(_:)), "]")])
        NSApp.mainMenu = main
        guard startServer() else {
            let a = NSAlert(); a.messageText = "Không khởi động được gl-ui.py"; a.runModal(); NSApp.terminate(nil); return
        }
        newWindow(nil)
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
