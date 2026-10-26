import Foundation
import Vision
while let line = readLine() {
 autoreleasepool {
  do {
   let input = try JSONSerialization.jsonObject(with:Data(line.utf8)) as! [String:String]
   let request = VNRecognizeTextRequest()
   request.recognitionLevel = .accurate
   request.usesLanguageCorrection = false
   request.recognitionLanguages = ["en-US", "zh-Hans"]
   let handler = VNImageRequestHandler(url:URL(fileURLWithPath:input["path"]!),options:[:])
   try handler.perform([request])
   let rows = (request.results ?? []).compactMap { r -> [String:Any]? in
    guard let t = r.topCandidates(1).first else {return nil}
    return ["text":t.string,"confidence":t.confidence]
   }
   let out:[String:Any] = ["path":input["path"]!,"lines":rows]
   let data = try JSONSerialization.data(withJSONObject:out)
   print(String(data:data,encoding:.utf8)!);fflush(stdout)
  } catch {print("{\"error\":\"OCR failed\"}");fflush(stdout)}
 }
}
