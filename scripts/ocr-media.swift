import Foundation
import Vision
import AppKit
for file in CommandLine.arguments.dropFirst() {
 do {
  let request = VNRecognizeTextRequest(); request.recognitionLevel = .accurate;request.usesLanguageCorrection = false; request.recognitionLanguages = ["en-US"]
  let handler=VNImageRequestHandler(url:URL(fileURLWithPath:file),options:[:]);try handler.perform([request])
  let lines=(request.results ?? []).compactMap{$0.topCandidates(1).first?.string}
  let data=try JSONSerialization.data(withJSONObject:["file":file,"lines":lines]);print(String(data:data,encoding:.utf8)!)
 }catch{print("{\"file\":\"\(file)\",\"error\":\"OCR failed\"}")}
}
