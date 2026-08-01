/** Mentor — hỏi đáp Socratic về tài chính hành vi và giao dịch. */
"use client";

import { PageHeader } from "@/components/common/PageHeader";
import { MentorChat } from "@/components/mentor/MentorChat";

export default function MentorPage() {
  return (
    <div>
      <PageHeader
        title="Mentor tài chính"
        description="Học cách tư duy như nhà đầu tư qua các câu hỏi gợi mở — không trao đáp án có sẵn."
      />
      <MentorChat />
    </div>
  );
}
