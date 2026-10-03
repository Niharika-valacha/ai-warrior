import { ContentProvider } from "@/components/ContentProvider";
import { HostApp } from "@/components/host/HostApp";
import { loadContent } from "@/lib/loadContent";

export const metadata = { title: "AI Warrior · Host" };

export default async function HostPage() {
  const { content } = await loadContent();
  return (
    <ContentProvider content={content}>
      <HostApp />
    </ContentProvider>
  );
}
