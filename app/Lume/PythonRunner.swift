import Foundation

struct CommandResult {
    let exitCode: Int32
    let cancelled: Bool
    let logURL: URL
}

// Processo em fila de fundo; nenhuma espera bloqueante ocorre na interface.
final class PythonRunner: @unchecked Sendable {
    static let shared = PythonRunner()
    private let lock = NSLock()
    private var process: Process?
    private var busy = false
    private var cancellationRequested = false

    private func begin() throws {
        lock.lock(); defer { lock.unlock() }
        guard !busy else { throw FonteError.message("Já existe uma operação em andamento.") }
        busy = true
        cancellationRequested = false
    }

    private func attach(_ task: Process) -> Bool {
        lock.lock(); defer { lock.unlock() }
        process = task
        return cancellationRequested
    }

    private func isCancelled() -> Bool {
        lock.lock(); defer { lock.unlock() }
        return cancellationRequested
    }

    private func finish() {
        lock.lock(); defer { lock.unlock() }
        process = nil
        busy = false
    }

    func cancel() {
        lock.lock()
        cancellationRequested = true
        let task = process
        lock.unlock()
        if let task = task, task.isRunning { task.terminate() }
    }

    /// `extraEnvironment` leva segredos (como a chave da API) ao motor sem expô-los nos argumentos do processo.
    func run(executable: URL, arguments: [String], directory: URL, logURL: URL,
             extraEnvironment: [String: String] = [:]) async throws -> CommandResult {
        try begin()
        return try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<CommandResult, Error>) in
            DispatchQueue.global(qos: .userInitiated).async {
                do {
                    let manager = FileManager.default
                    try manager.createDirectory(at: logURL.deletingLastPathComponent(), withIntermediateDirectories: true)
                    guard manager.createFile(atPath: logURL.path, contents: nil) else {
                        throw FonteError.message("Não foi possível criar o registro da operação.")
                    }
                    let output = try FileHandle(forWritingTo: logURL)
                    defer { try? output.close() }
                    let task = Process()
                    task.executableURL = executable
                    task.arguments = arguments // Sem interpolação de caminhos em comandos de shell.
                    task.currentDirectoryURL = directory
                    var environment = ProcessInfo.processInfo.environment
                    environment["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + (environment["PATH"] ?? "")
                    environment["PYTHONUNBUFFERED"] = "1"
                    environment["PYTHONDONTWRITEBYTECODE"] = "1"
                    environment.merge(extraEnvironment) { _, novo in novo }
                    task.environment = environment
                    // Arquivo, em vez de pipes: evita bloqueio quando a saída é volumosa.
                    task.standardOutput = output
                    task.standardError = output
                    task.standardInput = FileHandle.nullDevice
                    if self.attach(task) {
                        self.finish()
                        continuation.resume(returning: CommandResult(exitCode: 130, cancelled: true, logURL: logURL))
                        return
                    }
                    try task.run()
                    if self.isCancelled(), task.isRunning { task.terminate() }
                    task.waitUntilExit()
                    let result = CommandResult(exitCode: task.terminationStatus,
                                               cancelled: self.isCancelled(), logURL: logURL)
                    self.finish()
                    continuation.resume(returning: result)
                } catch {
                    self.finish()
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    static func tail(_ url: URL) -> String {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return "" }
        defer { try? handle.close() }
        do {
            let size = try handle.seekToEnd()
            try handle.seek(toOffset: size > 32_768 ? size - 32_768 : 0)
            let data = try handle.read(upToCount: 32_768) ?? Data()
            return String(decoding: data, as: UTF8.self)
        } catch { return "" }
    }

    /// Registro inteiro (até `limit` bytes). `tail` só guarda os últimos 32 KB, e linhas de protocolo grandes
    /// (resultados de dezenas de decisões, texto exato do pedido) passam disso e se perderiam.
    static func text(_ url: URL, limit: Int = 16_000_000) -> String {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return "" }
        defer { try? handle.close() }
        let data = (try? handle.read(upToCount: limit)) ?? Data()
        return String(decoding: data, as: UTF8.self)
    }

    /// `tail` sem chaves de API: para qualquer texto do registro que o app mostre ao usuário.
    static func safeTail(_ url: URL, secrets: [String] = []) -> String {
        SecretRedactor.redact(tail(url), secrets: secrets)
    }
}

/// Remove chaves de qualquer texto que o app possa exibir (erros, registro do motor).
enum SecretRedactor {
    static func redact(_ text: String, secrets: [String] = []) -> String {
        var result = text
        for secret in secrets where secret.count >= 8 { result = result.replacingOccurrences(of: secret, with: "[chave oculta]") }
        guard let pattern = try? NSRegularExpression(pattern: "sk-[A-Za-z0-9_\\-]{8,}") else { return result }
        return pattern.stringByReplacingMatches(in: result, range: NSRange(result.startIndex..., in: result),
                                                withTemplate: "[chave oculta]")
    }
}
