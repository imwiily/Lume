import Foundation

struct EngineManifest: Decodable {
    let package_schema: Int
    let api_version: Int
    let report_schema: Int
    let decision_schema: Int
    let engine_version: String
    let architecture: String
    let platform: String
    let executable: String
}

struct EmbeddedEngine {
    let root: URL
    let version: String
    let updated: Bool
    var executable: URL { root.appendingPathComponent("runtime/lume-engine") }

    static var support: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("FONTE", isDirectory: true)
    }
    static var bundledRoot: URL? {
        Bundle.main.resourceURL?.appendingPathComponent("Engine.lumemotor", isDirectory: true)
    }
    static var bundled: EmbeddedEngine? {
        guard let root = bundledRoot else { return nil }
        return read(root, updated: false)
    }
    private static func read(_ root: URL, updated: Bool) -> EmbeddedEngine? {
        guard let data = try? Data(contentsOf: root.appendingPathComponent("manifest.json")),
              let manifest = try? JSONDecoder().decode(EngineManifest.self, from: data),
              manifest.package_schema == 1, manifest.api_version == 1,
              manifest.report_schema == 1, manifest.decision_schema == 1,
              manifest.platform == "darwin", manifest.architecture == "arm64",
              manifest.executable == "runtime/lume-engine",
              FileManager.default.isExecutableFile(atPath: root.appendingPathComponent(manifest.executable).path)
        else { return nil }
        return EmbeddedEngine(root: root, version: manifest.engine_version, updated: updated)
    }
    static func resolve() -> (engine: EmbeddedEngine?, warning: String?) {
        guard let base = bundled else { return (nil, nil) }
        let state = support.appendingPathComponent("engine-state.json")
        guard FileManager.default.fileExists(atPath: state.path) else { return (base, nil) }
        if let data = try? Data(contentsOf: state),
           let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           object["schema_version"] as? Int == 1 {
            if object["active"] is NSNull { return (base, nil) }
            if let id = object["active"] as? String, id.count == 32,
               id.allSatisfy({ "0123456789abcdef".contains($0) }),
               let engine = read(support.appendingPathComponent("Engines/" + id), updated: true) {
                return (engine, nil)
            }
        }
        return (base, "A atualização não está disponível. O Lume carregou o motor embutido; use Restaurar embutido para reparar a seleção.")
    }
}
