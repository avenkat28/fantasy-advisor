import { PlayerSearch } from "@/components/player-search";
import { PageHeading, Panel } from "@/components/ui";
export default function PlayersPage() {
  return (
    <>
      <PageHeading
        eyebrow="PLAYER RESEARCH"
        title="Look beyond the box score."
        description="Find running backs and wide receivers. Explore the production behind the projection."
      />
      <Panel
        title="Find a player"
        subtitle="Search the local NFL dataset by partial first or last name"
      >
        <PlayerSearch />
      </Panel>
      <p className="disclaimer">
        Search includes historical players and observed roster members. A search
        result does not confirm that a player is available for an upcoming game.
      </p>
    </>
  );
}
