import { Lobby } from "@/components/lobby";
export default async function PlayPage({
  searchParams,
}: {
  searchParams: Promise<{ auth?: string }>;
}) {
  const { auth } = await searchParams;
  return <Lobby authStatus={auth} />;
}
