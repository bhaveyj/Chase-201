import { DraftScreen } from "@/components/draft";
export default async function DraftPage({
  params,
}: {
  params: Promise<{ draftId: string }>;
}) {
  const { draftId } = await params;
  return <DraftScreen id={draftId} />;
}
