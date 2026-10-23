import { PlayerProfile } from "@/components/player-profile";
export default async function PlayerPage({
  params,
}: {
  params: Promise<{ playerId: string }>;
}) {
  const { playerId } = await params;
  return <PlayerProfile id={playerId} />;
}
