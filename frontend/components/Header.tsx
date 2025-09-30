'use client';

import Link from 'next/link';
import { useState } from 'react';
import { ChatModal } from './ChatModal';

export function Header() {
  const [isChatOpen, setIsChatOpen] = useState(false);

  return (
    <>
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <Link href="/" className="text-2xl font-bold text-primary">
                DGRO
              </Link>
              <nav className="ml-10 flex space-x-8">
                <Link
                  href="/"
                  className="text-gray-700 hover:text-primary px-3 py-2 text-sm font-medium"
                >
                  Cases
                </Link>
              </nav>
            </div>
            <div className="flex items-center">
              <span className="text-sm text-gray-600 mr-4">
                {process.env.NEXT_PUBLIC_COMPANY_NAME || 'Your Company'}
              </span>
              <button
                onClick={() => setIsChatOpen(true)}
                className="bg-primary text-white px-4 py-2 rounded-lg hover:bg-blue-600 transition-colors"
              >
                New Case
              </button>
            </div>
          </div>
        </div>
      </header>
      <ChatModal isOpen={isChatOpen} onClose={() => setIsChatOpen(false)} />
    </>
  );
}
