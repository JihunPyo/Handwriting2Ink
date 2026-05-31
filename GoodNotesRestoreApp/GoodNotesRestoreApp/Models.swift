import Foundation

struct CreateJobResponse: Decodable {
    let jobId: String
    let status: String

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
        case status
    }
}

struct JobStatusResponse: Decodable {
    let jobId: String
    let status: String
    let message: String?
    let binaryReady: Bool
    let strokesReady: Bool
    let errorCode: String?
    let errorMessage: String?

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
        case status
        case message
        case binaryReady = "binary_ready"
        case strokesReady = "strokes_ready"
        case errorCode = "error_code"
        case errorMessage = "error_message"
    }
}
