import { ContentProvider } from "@/components/ContentProvider";
import { PlayerApp } from "@/components/play/PlayerApp";
import { loadContent } from "@/lib/loadContent";

export const metadata = { title: "AI Warrior · Join" };

export default async function PlayPage({ searchParams }: PageProps<"/play">) {
  const { room } = await searchParams;
  const { content } = await loadContent();
  return (
    <ContentProvider content={content}>
      <PlayerApp initialCode={typeof room === "string" ? room : ""} />
    </ContentProvider>
  );
}
