import PhotosUI
import SwiftUI

@MainActor
struct ContentView: View {
    @State private var serverURLText = "http://127.0.0.1:8000"
    @State private var selectedItem: PhotosPickerItem?
    @State private var imageData: Data?
    @State private var job: JobStatusResponse?
    @State private var createdJobId: String?
    @State private var isWorking = false
    @State private var message = "이미지를 선택하세요."
    @State private var errorMessage: String?

    private var apiClient: APIClient? {
        guard let baseURL = URL(string: serverURLText) else {
            return nil
        }
        return APIClient(baseURL: baseURL)
    }

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 20) {
                TextField("서버 URL", text: $serverURLText)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.URL)
                    .textFieldStyle(.roundedBorder)

                PhotosPicker(selection: $selectedItem, matching: .images) {
                    Label("이미지 선택", systemImage: "photo")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)

                if imageData != nil {
                    Button {
                        Task { await uploadAndPoll() }
                    } label: {
                        Label("서버로 업로드", systemImage: "arrow.up.doc")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .disabled(isWorking)
                }

                if let job {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Job ID: \(job.jobId)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("Status: \(job.status)")
                            .font(.headline)
                        Text(job.message ?? message)
                    }
                } else {
                    Text(message)
                        .font(.headline)
                }

                if job?.binaryReady == true, let createdJobId {
                    Button {
                        Task { await copyBinary(jobId: createdJobId) }
                    } label: {
                        Label("GoodNotes 클립보드에 복사", systemImage: "doc.on.clipboard")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                }

                if let errorMessage {
                    Text(errorMessage)
                        .foregroundStyle(.red)
                }

                Spacer()
            }
            .padding()
            .navigationTitle("GoodNotes 복원")
        }
        .onChange(of: selectedItem) { newItem in
            Task { await loadSelectedImage(newItem) }
        }
    }

    private func loadSelectedImage(_ item: PhotosPickerItem?) async {
        do {
            imageData = try await item?.loadTransferable(type: Data.self)
            job = nil
            createdJobId = nil
            errorMessage = nil
            message = imageData == nil ? "이미지를 선택하세요." : "이미지가 선택되었습니다."
        } catch {
            errorMessage = "이미지를 불러오지 못했습니다: \(error.localizedDescription)"
        }
    }

    private func uploadAndPoll() async {
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
            let created = try await apiClient.uploadImage(data: imageData, filename: "input.jpg")
            createdJobId = created.jobId
            try await poll(jobId: created.jobId, apiClient: apiClient)
        } catch {
            errorMessage = "처리에 실패했습니다: \(error.localizedDescription)"
        }
    }

    private func poll(jobId: String, apiClient: APIClient) async throws {
        while true {
            let current = try await apiClient.fetchJob(jobId: jobId)
            job = current

            if current.binaryReady || current.status == "failed" {
                return
            }

            try await Task.sleep(nanoseconds: 2_000_000_000)
        }
    }

    private func copyBinary(jobId: String) async {
        guard let apiClient else {
            errorMessage = "서버 URL이 올바르지 않습니다."
            return
        }
        do {
            let data = try await apiClient.downloadBinary(jobId: jobId)
            PasteboardWriter.writeGoodNotesBinary(data)
            try await apiClient.markDelivered(jobId: jobId)
            job = try await apiClient.fetchJob(jobId: jobId)
            message = "클립보드에 복사되었습니다. GoodNotes에서 붙여넣기 해주세요."
        } catch {
            errorMessage = "클립보드 기록에 실패했습니다: \(error.localizedDescription)"
        }
    }
}
