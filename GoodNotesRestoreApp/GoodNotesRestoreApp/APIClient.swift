import Foundation

enum APIClientError: LocalizedError {
    case invalidResponse
    case serverError(Int, String)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "서버 응답을 해석할 수 없습니다."
        case let .serverError(statusCode, message):
            if message.isEmpty {
                return "서버가 HTTP \(statusCode) 오류를 반환했습니다."
            }
            return "서버가 HTTP \(statusCode) 오류를 반환했습니다: \(message)"
        }
    }
}

final class APIClient {
    private let baseURL: URL
    private let session: URLSession

    init(
        baseURL: URL = URL(string: "http://127.0.0.1:8000")!,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.session = session
    }

    private func endpoint(_ path: String) -> URL {
        URL(string: path, relativeTo: baseURL)!.absoluteURL
    }

    func uploadImage(
        data: Data,
        filename: String,
        contentType: String = "image/jpeg"
    ) async throws -> CreateJobResponse {
        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: endpoint("/api/jobs"))
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        body.append("--\(boundary)\r\n")
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n")
        body.append("Content-Type: \(contentType)\r\n\r\n")
        body.append(data)
        body.append("\r\n--\(boundary)--\r\n")

        let (responseData, response) = try await session.upload(for: request, from: body)
        try validate(response: response, data: responseData)
        return try JSONDecoder().decode(CreateJobResponse.self, from: responseData)
    }

    func fetchJob(jobId: String) async throws -> JobStatusResponse {
        let url = endpoint("/api/jobs/\(jobId)")
        let (data, response) = try await session.data(from: url)
        try validate(response: response, data: data)
        return try JSONDecoder().decode(JobStatusResponse.self, from: data)
    }

    func downloadBinary(jobId: String) async throws -> Data {
        let url = endpoint("/api/jobs/\(jobId)/binary")
        let (data, response) = try await session.data(from: url)
        try validate(response: response, data: data)
        return data
    }

    func markDelivered(jobId: String) async throws {
        var request = URLRequest(url: endpoint("/api/jobs/\(jobId)/delivered"))
        request.httpMethod = "POST"
        let (data, response) = try await session.data(for: request)
        try validate(response: response, data: data)
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIClientError.invalidResponse
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            let message = parseErrorMessage(from: data)
            throw APIClientError.serverError(httpResponse.statusCode, message)
        }
    }

    private func parseErrorMessage(from data: Data) -> String {
        if let response = try? JSONDecoder().decode(APIErrorResponse.self, from: data),
           let detail = response.detail {
            return detail
        }
        return String(data: data, encoding: .utf8) ?? ""
    }
}

private struct APIErrorResponse: Decodable {
    let detail: String?
}

private extension Data {
    mutating func append(_ string: String) {
        append(Data(string.utf8))
    }
}
