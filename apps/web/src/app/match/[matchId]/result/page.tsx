import { MatchScreen } from "@/components/match";
export default async function ResultPage({
  params,
}: {
  params: Promise<{ matchId: string }>;
}) {
  const { matchId } = await params;
  return <MatchScreen id={matchId} result />;
}
