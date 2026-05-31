import PhotosUI
import SwiftUI
import UIKit

@MainActor
struct ContentView: View {
    @AppStorage("serverURLText") private var serverURLText = "https://handwriting2ink-production.up.railway.app"
    @State private var selectedItem: PhotosPickerItem?
    @State private var imageData: Data?
    @State private var previewImage: UIImage?
    @State private var job: JobStatusResponse?
    @State private var createdJobId: String?
    @State private var isWorking = false
    @State private var message = "이미지를 선택하면 서버 처리와 GoodNotes 클립보드 복사를 순서대로 실행할 수 있습니다."
    @State private var errorMessage: String?
    @State private var copiedByteCount: Int?

    private var apiClient: APIClient? {
        guard let baseURL = normalizedServerURL else {
            return nil
        }
        return APIClient(baseURL: baseURL)
    }

    private var normalizedServerURL: URL? {
        let trimmed = serverURLText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: trimmed),
              let scheme = url.scheme?.lowercased(),
              ["http", "https"].contains(scheme),
              url.host != nil else {
            return nil
        }
        return url
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("서버") {
                    TextField("서버 URL", text: $serverURLText)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)

                    if normalizedServerURL == nil {
                        Text("http:// 또는 https://로 시작하는 서버 URL이 필요합니다.")
                            .font(.caption)
                            .foregroundStyle(.red)
                    }
                }

                Section("이미지") {
                    PhotosPicker(selection: $selectedItem, matching: .images) {
                        Label(imageData == nil ? "이미지 선택" : "다른 이미지 선택", systemImage: "photo")
                    }

                    if let previewImage {
                        Image(uiImage: previewImage)
                            .resizable()
                            .scaledToFit()
                            .frame(maxHeight: 280)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                }

                Section("실행") {
                    Button {
                        Task { await runRestore() }
                    } label: {
                        Label("GoodNotes 클립보드로 복원", systemImage: "doc.on.clipboard")
                    }
                    .disabled(imageData == nil || isWorking || normalizedServerURL == nil)

                    if isWorking {
                        ProgressView(message)
                    } else {
                        Text(message)
                    }
                }

                if let job {
                    Section("Job 상태") {
                        LabeledContent("Job ID", value: job.jobId)
                        LabeledContent("상태", value: job.status)
                        LabeledContent("strokes.json", value: job.strokesReady ? "준비됨" : "대기 중")
                        LabeledContent("GoodNotes binary", value: job.binaryReady ? "준비됨" : "대기 중")
                        if let jobMessage = job.message {
                            Text(jobMessage)
                        }
                        if let copiedByteCount {
                            LabeledContent("클립보드 기록", value: "\(copiedByteCount) bytes")
                        }
                    }
                }

                if job?.binaryReady == true, let createdJobId {
                    Section("재시도") {
                        Button {
                            Task { await copyBinary(jobId: createdJobId) }
                        } label: {
                            Label("binary 다시 다운로드 후 복사", systemImage: "arrow.clockwise")
                        }
                        .disabled(isWorking)
                    }
                }

                if let errorMessage {
                    Section("오류") {
                        Text(errorMessage)
                            .foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle("GoodNotes 복원")
        }
        .onChange(of: selectedItem) { newItem in
            Task { await loadSelectedImage(newItem) }
        }
    }

    private func loadSelectedImage(_ item: PhotosPickerItem?) async {
        do {
            let selectedData = try await item?.loadTransferable(type: Data.self)
            if let selectedData,
               let image = UIImage(data: selectedData),
               let jpegData = image.jpegData(compressionQuality: 0.95) {
                imageData = jpegData
                previewImage = image
            } else {
                imageData = nil
                previewImage = nil
            }
            job = nil
            createdJobId = nil
            copiedByteCount = nil
            errorMessage = nil
            message = imageData == nil ? "이미지를 선택하세요." : "이미지가 선택되었습니다. 복원을 실행할 수 있습니다."
        } catch {
            errorMessage = "이미지를 불러오지 못했습니다: \(error.localizedDescription)"
        }
    }

    private func runRestore() async {
        guard let imageData else { return }
        guard let apiClient else {
            errorMessage = "서버 URL이 올바르지 않습니다."
            return
        }
        isWorking = true
        errorMessage = nil
        defer { isWorking = false }

        do {
            message = "이미지를 업로드하고 있습니다."
            let created = try await apiClient.uploadImage(
                data: imageData,
                filename: "input.jpg",
                contentType: "image/jpeg"
            )
            createdJobId = created.jobId
            let finishedJob = try await poll(jobId: created.jobId, apiClient: apiClient)
            guard finishedJob.status != "failed" else {
                throw RestoreError.jobFailed(finishedJob.errorMessage ?? finishedJob.message ?? "서버 job이 실패했습니다.")
            }
            try await copyBinary(jobId: created.jobId, apiClient: apiClient)
        } catch {
            errorMessage = "처리에 실패했습니다: \(error.localizedDescription)"
        }
    }

    private func poll(jobId: String, apiClient: APIClient) async throws -> JobStatusResponse {
        while true {
            let current = try await apiClient.fetchJob(jobId: jobId)
            job = current
            message = current.message ?? "서버 처리를 기다리고 있습니다."

            if current.binaryReady || current.status == "failed" {
                return current
            }

            try await Task.sleep(nanoseconds: 2_000_000_000)
        }
    }

    private func copyBinary(jobId: String) async {
        guard let apiClient else {
            errorMessage = "서버 URL이 올바르지 않습니다."
            return
        }
        isWorking = true
        defer { isWorking = false }

        do {
            try await copyBinary(jobId: jobId, apiClient: apiClient)
        } catch {
            errorMessage = "클립보드 기록에 실패했습니다: \(error.localizedDescription)"
        }
    }

    private func copyBinary(jobId: String, apiClient: APIClient) async throws {
        message = "GoodNotes binary를 다운로드하고 있습니다."
        let data = try await apiClient.downloadBinary(jobId: jobId)
        PasteboardWriter.writeGoodNotesBinary(data)
        copiedByteCount = data.count
        message = "클립보드에 복사되었습니다. GoodNotes에서 붙여넣기 하면 됩니다."
        try await apiClient.markDelivered(jobId: jobId)
        job = try await apiClient.fetchJob(jobId: jobId)
    }
}

private enum RestoreError: LocalizedError {
    case jobFailed(String)

    var errorDescription: String? {
        switch self {
        case let .jobFailed(message):
            return message
        }
    }
}
