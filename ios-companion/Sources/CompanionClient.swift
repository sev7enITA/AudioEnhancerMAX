import Foundation
import Security
import CryptoKit

struct Pairing: Codable, Equatable {
    let `protocol`:Int
    let endpoint:String
    let fingerprint:String
    let token:String
    static func parse(_ text:String) throws -> Pairing {
        guard text.utf8.count<4096,let data=text.data(using:.utf8) else {throw CompanionError.message("Invalid pairing code.")}
        return try JSONDecoder().decode(Pairing.self,from:data).validated()
    }

    func validated() throws -> Pairing {
        guard self.protocol==1, let url=URLComponents(string:endpoint), url.scheme=="https",url.host != nil,
              url.user==nil,url.password==nil,url.query==nil,url.fragment==nil,["","/"].contains(url.path),
              fingerprint.count==64,fingerprint.allSatisfy({"0123456789abcdef".contains($0)}),
              (32...128).contains(token.count),token.allSatisfy({$0.isASCII && ($0.isLetter || $0.isNumber || $0=="_" || $0=="-")}) else {
            throw CompanionError.message("Use the complete pairing code from this Mac’s Settings.")
        }
        return self
    }
}

final class PinnedSession: NSObject, URLSessionDelegate, URLSessionTaskDelegate, @unchecked Sendable {
    private let host: String?
    private let fingerprint: String

    init(endpoint: URL?, fingerprint: String) {
        self.host = endpoint?.host
        self.fingerprint = fingerprint
    }
    func urlSession(_ session:URLSession,didReceive challenge:URLAuthenticationChallenge,completionHandler:@escaping(URLSession.AuthChallengeDisposition,URLCredential?)->Void) {
        guard challenge.protectionSpace.authenticationMethod==NSURLAuthenticationMethodServerTrust,
              challenge.protectionSpace.host==host,
              let trust=challenge.protectionSpace.serverTrust,
              let chain=SecTrustCopyCertificateChain(trust) as? [SecCertificate],let certificate=chain.first else {
            completionHandler(.cancelAuthenticationChallenge,nil);return
        }
        let digest=SHA256.hash(data:SecCertificateCopyData(certificate) as Data).map{String(format:"%02x",$0)}.joined()
        if digest==fingerprint {completionHandler(.useCredential,URLCredential(trust:trust))}
        else {completionHandler(.cancelAuthenticationChallenge,nil)}
    }
    func urlSession(_ session: URLSession, task: URLSessionTask, didReceive challenge: URLAuthenticationChallenge,
                    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        urlSession(session, didReceive: challenge, completionHandler: completionHandler)
    }

    func urlSession(_ session:URLSession,task:URLSessionTask,willPerformHTTPRedirection response:HTTPURLResponse,newRequest request:URLRequest,completionHandler:@escaping(URLRequest?)->Void) {completionHandler(nil)}
}

final class CompanionClient: @unchecked Sendable {
    let pairing:Pairing
    let device:String
    private let delegate:PinnedSession
    private let session:URLSession
    init(_ pairing:Pairing,device:String) {
        self.pairing=pairing;self.device=device;delegate=PinnedSession(endpoint:URL(string:pairing.endpoint),fingerprint:pairing.fingerprint)
        let config=URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest=30;config.timeoutIntervalForResource=180
        config.httpShouldSetCookies=false;config.urlCache=nil
        session=URLSession(configuration:config,delegate:delegate,delegateQueue:nil)
    }
    func invalidate(){session.invalidateAndCancel()}
    func request(_ path:String,method:String="GET",body:Data?=nil,extension ext:String?=nil) async throws -> (Data,HTTPURLResponse) {
        guard path.hasPrefix("/v1/"),let url=URL(string:pairing.endpoint+path) else {throw CompanionError.message("Invalid request.")}
        var req=URLRequest(url:url);req.httpMethod=method;req.httpBody=body
        req.setValue("Bearer \(pairing.token)",forHTTPHeaderField:"Authorization")
        req.setValue(await DeviceAssessment.header(),forHTTPHeaderField:"X-Device-Assessment")
        req.setValue(device,forHTTPHeaderField:"X-Device-ID")
        req.setValue("iOS companion",forHTTPHeaderField:"X-Device-Name")
        req.setValue(String(ProcessInfo.processInfo.activeProcessorCount),forHTTPHeaderField:"X-Device-Cores")
        req.setValue("application/json",forHTTPHeaderField:"Content-Type")
        if let ext { req.setValue(ext,forHTTPHeaderField:"X-Audio-Extension");req.setValue("application/octet-stream",forHTTPHeaderField:"Content-Type") }
        let (data,response)=try await session.data(for:req)
        guard let http=response as? HTTPURLResponse else {throw CompanionError.message("Invalid Mac response.")}
        guard http.statusCode==200 else {
            let json=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any]
            throw CompanionError.message(json?["error"] as? String ?? "Mac returned HTTP \(http.statusCode).")
        }
        guard data.count<=32*1024*1024 else {throw CompanionError.message("Mac response exceeds the limit.")}
        return (data,http)
    }
    func json(_ path:String,method:String="GET",body:[String:String]?=nil) async throws -> [String:Any] {
        let payload=try body.map{try JSONSerialization.data(withJSONObject:$0)}
        let (data,_)=try await request(path,method:method,body:payload)
        guard let value=try JSONSerialization.jsonObject(with:data) as? [String:Any] else {throw CompanionError.message("Invalid Mac response.")}
        return value
    }
}

enum PairingStore {
    private static let base:[String:Any]=[kSecClass as String:kSecClassGenericPassword,kSecAttrService as String:"AudioEnhancerCompanion",kSecAttrAccount as String:"pairedMac"]
    static func save(_ pairing:Pairing) throws {
        let data=try JSONEncoder().encode(pairing)
        let changes:[String:Any]=[kSecValueData as String:data,kSecAttrAccessible as String:kSecAttrAccessibleWhenUnlockedThisDeviceOnly]
        let status=SecItemUpdate(base as CFDictionary,changes as CFDictionary)
        if status==errSecSuccess{return}
        guard status==errSecItemNotFound else {throw CompanionError.message("Could not update the pairing securely.")}
        var query=base;changes.forEach{query[$0.key]=$0.value}
        guard SecItemAdd(query as CFDictionary,nil)==errSecSuccess else {throw CompanionError.message("Could not store the pairing securely.")}
    }
    static func load()->Pairing? {
        var query=base;query[kSecReturnData as String]=true;query[kSecMatchLimit as String]=kSecMatchLimitOne
        var value:CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary,&value)==errSecSuccess,let data=value as? Data,let text=String(data:data,encoding:.utf8) else {return nil}
        return try? Pairing.parse(text)
    }
    static func clear(){SecItemDelete(base as CFDictionary)}
}
