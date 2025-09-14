import Foundation

struct CaseModel: Identifiable {
    let id: Int
    let subject: String
    let features: String
    let location: String
    let budget: Double
    let timeline: String
    let additionalFeatures: String
}

struct UserModel: Identifiable {
    let id: Int
    let caseId: Int
    let name: String
    let email: String
    let phone: String
}

struct EmailCommunication: Identifiable {
    let id: Int
    let caseId: Int
    let vendorEmail: String
    let vendorName: String
    let vendorWebsite: String
    let subject: String
    let messageId: String
    let threadId: String
    let emailType: String
    let emailContent: String
    let sentAt: Date
    let status: String
}
