/** Tin tức — bước 1 của hành trình: đọc tin & cảm nhận thị trường. */
"use client";

import { useEffect } from "react";

import { PageHeader } from "@/components/common/PageHeader";
import { NewsFilter } from "@/components/news/NewsFilter";
import { NewsList } from "@/components/news/NewsList";
import { useNewsStore } from "@/store/useNewsStore";

export default function NewsPage() {
  const fetchNews = useNewsStore((state) => state.fetchNews);

  useEffect(() => {
    void fetchNews();
  }, [fetchNews]);

  return (
    <div>
      <PageHeader
        title="Tin tức & Cảm xúc thị trường"
        description="Nắm bắt các sự kiện vĩ mô, ngành và doanh nghiệp kèm mức tác động tới giá."
      />
      <NewsFilter />
      <NewsList />
    </div>
  );
}
