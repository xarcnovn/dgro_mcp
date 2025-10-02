'use client';

import { useState } from 'react';
import { EmailCommunication } from '@/lib/types';

interface EmailThreadsProps {
  communications: EmailCommunication[];
}

export function EmailThreads({ communications }: EmailThreadsProps) {
  const [expandedThreads, setExpandedThreads] = useState<Set<string>>(new Set());

  if (communications.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No communications yet
      </div>
    );
  }

  // Group by thread_id
  const threads = communications.reduce((acc, email) => {
    const threadId = email.thread_id || `single-${email.id}`;
    if (!acc[threadId]) {
      acc[threadId] = [];
    }
    acc[threadId].push(email);
    return acc;
  }, {} as Record<string, EmailCommunication[]>);

  const toggleThread = (threadId: string) => {
    const newExpanded = new Set(expandedThreads);
    if (newExpanded.has(threadId)) {
      newExpanded.delete(threadId);
    } else {
      newExpanded.add(threadId);
    }
    setExpandedThreads(newExpanded);
  };

  return (
    <div className="space-y-4">
      {Object.entries(threads).map(([threadId, emails]) => {
        const isExpanded = expandedThreads.has(threadId);
        const firstEmail = emails[0];

        return (
          <div key={threadId} className="border border-gray-200 rounded-lg">
            <div
              className="p-4 cursor-pointer hover:bg-gray-50"
              onClick={() => toggleThread(threadId)}
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <h4 className="font-medium text-gray-900">
                    {firstEmail.subject}
                  </h4>
                  <p className="text-sm text-gray-600 mt-1">
                    {firstEmail.vendor_email}
                  </p>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs text-gray-500">
                    {emails.length} message{emails.length > 1 ? 's' : ''}
                  </span>
                  <svg
                    className={`w-5 h-5 text-gray-500 transition-transform ${
                      isExpanded ? 'transform rotate-180' : ''
                    }`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 9l-7 7-7-7"
                    />
                  </svg>
                </div>
              </div>
            </div>

            {isExpanded && (
              <div className="border-t border-gray-200">
                {emails.map((email) => (
                  <div
                    key={email.id}
                    className={`p-4 ${
                      email.email_type === 'initial_outreach' || email.email_type === 'reply'
                        ? 'bg-blue-50'
                        : 'bg-gray-50'
                    }`}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs font-medium px-2 py-1 rounded ${
                            email.email_type === 'initial_outreach' || email.email_type === 'reply'
                              ? 'bg-blue-100 text-blue-800'
                              : 'bg-gray-200 text-gray-700'
                          }`}
                        >
                          {email.email_type}
                        </span>
                        {email.vendor_name && (
                          <span className="text-xs text-gray-600">
                            {email.vendor_name}
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-gray-500">
                        {new Date(email.sent_at).toLocaleString()}
                      </span>
                    </div>
                    <div
                      className="text-sm text-gray-700"
                      dangerouslySetInnerHTML={{ __html: email.email_content }}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
