// Vẽ icon Graylog.app: nền bo góc xanh đậm, ba dòng log, kính lúp. Dùng: swift gl-icon.swift out.png
import Cocoa

let S: CGFloat = 1024
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(S), pixelsHigh: Int(S), bitsPerSample: 8,
                           samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                           bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)

// nền (chừa lề như icon macOS)
let bg = NSBezierPath(roundedRect: NSRect(x: 100, y: 100, width: 824, height: 824), xRadius: 185, yRadius: 185)
NSGradient(colors: [NSColor(red: 0.16, green: 0.42, blue: 0.95, alpha: 1), NSColor(red: 0.05, green: 0.13, blue: 0.38, alpha: 1)])!
    .draw(in: bg, angle: -90)

// các dòng log: chấm mức độ + thanh chữ
let rows: [(CGFloat, NSColor, CGFloat)] = [(690, NSColor(red: 0.45, green: 0.9, blue: 0.6, alpha: 1), 430),
                                           (570, NSColor(red: 1, green: 0.8, blue: 0.3, alpha: 1), 330),
                                           (450, NSColor(red: 1, green: 0.42, blue: 0.42, alpha: 1), 250),
                                           (330, NSColor(red: 0.45, green: 0.9, blue: 0.6, alpha: 1), 190)]
for (y, dot, w) in rows {
    dot.setFill(); NSBezierPath(ovalIn: NSRect(x: 215, y: y - 30, width: 60, height: 60)).fill()
    NSColor(white: 1, alpha: 0.9).setFill()
    NSBezierPath(roundedRect: NSRect(x: 315, y: y - 22, width: w, height: 44), xRadius: 22, yRadius: 22).fill()
}

// kính lúp
let c = NSPoint(x: 640, y: 410), r: CGFloat = 135
NSColor(red: 0.07, green: 0.18, blue: 0.48, alpha: 0.92).setFill()
NSBezierPath(ovalIn: NSRect(x: c.x - r, y: c.y - r, width: 2 * r, height: 2 * r)).fill()
NSColor.white.setStroke()
let ring = NSBezierPath(ovalIn: NSRect(x: c.x - r, y: c.y - r, width: 2 * r, height: 2 * r)); ring.lineWidth = 44; ring.stroke()
let handle = NSBezierPath(); handle.lineWidth = 58; handle.lineCapStyle = .round
handle.move(to: NSPoint(x: c.x + 108, y: c.y - 108)); handle.line(to: NSPoint(x: c.x + 200, y: c.y - 200)); handle.stroke()

try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
