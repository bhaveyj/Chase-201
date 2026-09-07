import { MatchScreen } from "@/components/match";
export default async function MatchPage({
  params,
}: {
  params: Promise<{ matchId: string }>;
}) {
  const { matchId } = await params;
  return <MatchScreen id={matchId} />;
}
