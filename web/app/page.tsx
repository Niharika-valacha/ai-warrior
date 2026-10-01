import Game from "@/components/Game";
import { ContentProvider } from "@/components/ContentProvider";
import { loadContent } from "@/lib/loadContent";

export default async function Page() {
  const { content } = await loadContent();
  return (
    <ContentProvider content={content}>
      <Game />
    </ContentProvider>
  );
}
