import { TeamScreen } from "@/components/team";
export default async function TeamPage({
  params,
}: {
  params: Promise<{ draftId: string }>;
}) {
  const { draftId } = await params;
  return <TeamScreen id={draftId} />;
}
