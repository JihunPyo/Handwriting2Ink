import CoreGraphics
import Darwin
import Foundation

private struct ReplayPoint: Decodable {
    let x: Double
    let y: Double

    init(from decoder: Decoder) throws {
        var container = try decoder.unkeyedContainer()
        x = try container.decode(Double.self)
        y = try container.decode(Double.self)
        if !container.isAtEnd {
            _ = try? container.decode(Double.self)
        }
    }

    var cgPoint: CGPoint {
        CGPoint(x: x, y: y)
    }
}

private struct ReplayPayload: Decodable {
    let kind: String
    let strokes: [[ReplayPoint]]?
    let points: [ReplayPoint]?
    let pointDelay: Double?
    let strokeDelay: Double?
    let mouseDownDelay: Double?
    let minStrokeDuration: Double?
    let eventInterval: Double?
    let strokeVelocity: Double?
    let dragDuration: Double?

    enum CodingKeys: String, CodingKey {
        case kind
        case strokes
        case points
        case pointDelay = "point_delay"
        case strokeDelay = "stroke_delay"
        case mouseDownDelay = "mouse_down_delay"
        case minStrokeDuration = "min_stroke_duration"
        case eventInterval = "event_interval"
        case strokeVelocity = "stroke_velocity"
        case dragDuration = "drag_duration"
    }
}

private struct CliOptions {
    let payloadPath: String
    let dryRun: Bool
}

private enum ReplayError: Error, CustomStringConvertible {
    case usage(String)
    case invalidPayload(String)
    case eventCreationFailed(String)
    case interrupted

    var description: String {
        switch self {
        case .usage(let message), .invalidPayload(let message), .eventCreationFailed(let message):
            return message
        case .interrupted:
            return "Replay was interrupted."
        }
    }
}

private var wasInterrupted = false
private let eventSource = CGEventSource(stateID: .hidSystemState)

private func signalHandler(_ signal: Int32) {
    wasInterrupted = true
}

private func printUsage() {
    fputs(
        """
        Usage: goodnotes_quartz_replay --payload <payload.json> [--dry-run]

        Payload kinds:
          strokes   { "kind": "strokes", "strokes": [[[x, y], ...]], "point_delay": 0.0005, "stroke_delay": 0.005 }
          drag_path { "kind": "drag_path", "points": [[x, y], ...], "drag_duration": 1.5 }

        """,
        stderr
    )
}

private func parseOptions() throws -> CliOptions {
    var payloadPath: String?
    var dryRun = false
    var index = 1
    let arguments = CommandLine.arguments

    while index < arguments.count {
        let argument = arguments[index]
        switch argument {
        case "--payload":
            index += 1
            guard index < arguments.count else {
                throw ReplayError.usage("--payload requires a path.")
            }
            payloadPath = arguments[index]
        case "--dry-run":
            dryRun = true
        case "--help", "-h":
            printUsage()
            exit(0)
        default:
            if payloadPath == nil && !argument.hasPrefix("-") {
                payloadPath = argument
            } else {
                throw ReplayError.usage("Unknown argument: \(argument)")
            }
        }
        index += 1
    }

    guard let payloadPath else {
        throw ReplayError.usage("--payload is required.")
    }
    return CliOptions(payloadPath: payloadPath, dryRun: dryRun)
}

private func sleepSeconds(_ seconds: Double) throws {
    let clamped = max(seconds, 0.0)
    guard clamped > 0 else {
        if wasInterrupted {
            throw ReplayError.interrupted
        }
        return
    }

    let microseconds = useconds_t(min(clamped * 1_000_000.0, Double(useconds_t.max)))
    usleep(microseconds)
    if wasInterrupted {
        throw ReplayError.interrupted
    }
}

private func distance(_ start: CGPoint, _ end: CGPoint) -> Double {
    hypot(end.x - start.x, end.y - start.y)
}

private func pathLength(_ points: [ReplayPoint]) -> Double {
    guard points.count >= 2 else {
        return 0.0
    }
    return zip(points, points.dropFirst()).reduce(0.0) { total, pair in
        total + distance(pair.0.cgPoint, pair.1.cgPoint)
    }
}

private func pointOnPath(_ points: [ReplayPoint], atDistance targetDistance: Double) -> CGPoint {
    guard points.count >= 2 else {
        return points.first?.cgPoint ?? .zero
    }
    if targetDistance <= 0 {
        return points[0].cgPoint
    }

    var remaining = targetDistance
    for (startPoint, endPoint) in zip(points, points.dropFirst()) {
        let start = startPoint.cgPoint
        let end = endPoint.cgPoint
        let segmentLength = distance(start, end)
        if segmentLength <= 0 {
            continue
        }
        if remaining <= segmentLength {
            let ratio = remaining / segmentLength
            return CGPoint(
                x: start.x + (end.x - start.x) * ratio,
                y: start.y + (end.y - start.y) * ratio
            )
        }
        remaining -= segmentLength
    }
    return points.last?.cgPoint ?? .zero
}

private func pacedPath(points: [ReplayPoint], duration: Double, eventInterval: Double) -> [CGPoint] {
    let totalLength = pathLength(points)
    guard totalLength > 0 else {
        return points.last.map { [$0.cgPoint] } ?? []
    }

    let interval = max(eventInterval, 0.001)
    let stepCount = max(1, Int(ceil(max(duration, interval) / interval)))
    return (1...stepCount).map { index in
        pointOnPath(points, atDistance: totalLength * Double(index) / Double(stepCount))
    }
}

private func postMouseEvent(_ type: CGEventType, at point: CGPoint) throws {
    guard let event = CGEvent(
        mouseEventSource: eventSource,
        mouseType: type,
        mouseCursorPosition: point,
        mouseButton: .left
    ) else {
        throw ReplayError.eventCreationFailed("Failed to create mouse event: \(type.rawValue)")
    }
    event.setIntegerValueField(.mouseEventClickState, value: 1)
    event.setIntegerValueField(.mouseEventButtonNumber, value: 0)
    event.setDoubleValueField(.mouseEventPressure, value: type == .leftMouseUp ? 0.0 : 1.0)
    event.flags = CGEventFlags(rawValue: event.flags.rawValue | CGEventFlags.maskNonCoalesced.rawValue)
    event.post(tap: .cghidEventTap)
}

private func summarize(_ payload: ReplayPayload) throws {
    switch payload.kind {
    case "strokes":
        let strokes = payload.strokes ?? []
        let pointCount = strokes.reduce(0) { total, stroke in total + stroke.count }
        guard !strokes.isEmpty && pointCount > 0 else {
            throw ReplayError.invalidPayload("strokes payload requires at least one point.")
        }
        print("kind: strokes")
        print("stroke count: \(strokes.count)")
        print("point count: \(pointCount)")
        print("point delay: \(payload.pointDelay ?? 0.0)")
        print("stroke delay: \(payload.strokeDelay ?? 0.0)")
        print("mouse down delay: \(payload.mouseDownDelay ?? 0.0)")
        print("min stroke duration: \(payload.minStrokeDuration ?? 0.0)")
        print("event interval: \(payload.eventInterval ?? 0.0)")
        print("stroke velocity: \(payload.strokeVelocity ?? 0.0)")
    case "drag_path":
        let points = payload.points ?? []
        guard points.count >= 2 else {
            throw ReplayError.invalidPayload("drag_path payload requires at least two points.")
        }
        print("kind: drag_path")
        print("point count: \(points.count)")
        print("drag duration: \(payload.dragDuration ?? 0.0)")
        print("mouse down delay: \(payload.mouseDownDelay ?? 0.0)")
    default:
        throw ReplayError.invalidPayload("Unsupported payload kind: \(payload.kind)")
    }
}

private func replayStrokes(
    _ strokes: [[ReplayPoint]],
    pointDelay: Double,
    strokeDelay: Double,
    mouseDownDelay: Double,
    minStrokeDuration: Double,
    eventInterval: Double,
    strokeVelocity: Double
) throws {
    var mouseIsDown = false
    var lastPoint: CGPoint?

    func releaseMouseIfNeeded() {
        if mouseIsDown, let point = lastPoint {
            try? postMouseEvent(.leftMouseUp, at: point)
            mouseIsDown = false
        }
    }

    defer {
        releaseMouseIfNeeded()
    }

    for stroke in strokes {
        guard stroke.count >= 2 else {
            continue
        }
        if wasInterrupted {
            throw ReplayError.interrupted
        }

        let start = stroke[0].cgPoint
        lastPoint = start
        try postMouseEvent(.mouseMoved, at: start)
        try postMouseEvent(.leftMouseDown, at: start)
        mouseIsDown = true
        try sleepSeconds(mouseDownDelay)

        let length = pathLength(stroke)
        let durationFromVelocity = strokeVelocity > 0 ? length / strokeVelocity : 0.0
        let targetDuration = max(minStrokeDuration, durationFromVelocity)
        if strokeVelocity > 0 && eventInterval > 0 {
            let points = pacedPath(points: stroke, duration: targetDuration, eventInterval: eventInterval)
            let stepDelay = max(targetDuration, 0.0) / Double(max(points.count, 1))
            for point in points {
                if wasInterrupted {
                    throw ReplayError.interrupted
                }
                lastPoint = point
                try postMouseEvent(.leftMouseDragged, at: point)
                try sleepSeconds(stepDelay)
            }
        } else {
            for point in stroke.dropFirst() {
                if wasInterrupted {
                    throw ReplayError.interrupted
                }
                let cgPoint = point.cgPoint
                lastPoint = cgPoint
                try postMouseEvent(.leftMouseDragged, at: cgPoint)
                try sleepSeconds(pointDelay)
            }
        }

        let scheduledDuration = max(mouseDownDelay, 0.0) + max(targetDuration, Double(max(stroke.count - 1, 0)) * max(pointDelay, 0.0))
        try sleepSeconds(max(minStrokeDuration, 0.0) - scheduledDuration)
        try postMouseEvent(.leftMouseUp, at: lastPoint ?? start)
        mouseIsDown = false
        try sleepSeconds(strokeDelay)
    }
}

private func replayDragPath(_ points: [ReplayPoint], dragDuration: Double, mouseDownDelay: Double) throws {
    guard points.count >= 2 else {
        throw ReplayError.invalidPayload("drag_path payload requires at least two points.")
    }

    var mouseIsDown = false
    var lastPoint: CGPoint?

    func releaseMouseIfNeeded() {
        if mouseIsDown, let point = lastPoint {
            try? postMouseEvent(.leftMouseUp, at: point)
            mouseIsDown = false
        }
    }

    defer {
        releaseMouseIfNeeded()
    }

    let start = points[0].cgPoint
    let segmentDelay = max(dragDuration, 0.0) / Double(max(points.count - 1, 1))
    lastPoint = start
    try postMouseEvent(.mouseMoved, at: start)
    try postMouseEvent(.leftMouseDown, at: start)
    mouseIsDown = true
    try sleepSeconds(mouseDownDelay)

    for point in points.dropFirst() {
        if wasInterrupted {
            throw ReplayError.interrupted
        }
        let cgPoint = point.cgPoint
        lastPoint = cgPoint
        try postMouseEvent(.leftMouseDragged, at: cgPoint)
        try sleepSeconds(segmentDelay)
    }

    try postMouseEvent(.leftMouseUp, at: lastPoint ?? start)
    mouseIsDown = false
}

private func replay(_ payload: ReplayPayload) throws {
    switch payload.kind {
    case "strokes":
        guard let strokes = payload.strokes else {
            throw ReplayError.invalidPayload("strokes payload is missing strokes.")
        }
        try replayStrokes(
            strokes,
            pointDelay: payload.pointDelay ?? 0.0,
            strokeDelay: payload.strokeDelay ?? 0.0,
            mouseDownDelay: payload.mouseDownDelay ?? 0.0,
            minStrokeDuration: payload.minStrokeDuration ?? 0.0,
            eventInterval: payload.eventInterval ?? 0.0,
            strokeVelocity: payload.strokeVelocity ?? 0.0
        )
    case "drag_path":
        guard let points = payload.points else {
            throw ReplayError.invalidPayload("drag_path payload is missing points.")
        }
        try replayDragPath(
            points,
            dragDuration: payload.dragDuration ?? 0.0,
            mouseDownDelay: payload.mouseDownDelay ?? 0.0
        )
    default:
        throw ReplayError.invalidPayload("Unsupported payload kind: \(payload.kind)")
    }
}

private func main() -> Int32 {
    signal(SIGINT, signalHandler)
    signal(SIGTERM, signalHandler)

    do {
        let options = try parseOptions()
        let data = try Data(contentsOf: URL(fileURLWithPath: options.payloadPath))
        let payload = try JSONDecoder().decode(ReplayPayload.self, from: data)
        try summarize(payload)
        if options.dryRun {
            print("dry-run: Quartz mouse events were not posted.")
            return 0
        }
        try replay(payload)
        print("done")
        return 0
    } catch ReplayError.usage(let message) {
        fputs("Usage error: \(message)\n", stderr)
        printUsage()
        return 2
    } catch ReplayError.interrupted {
        fputs("Replay was interrupted.\n", stderr)
        return 130
    } catch {
        fputs("Quartz replay failed: \(error)\n", stderr)
        return 3
    }
}

exit(main())
