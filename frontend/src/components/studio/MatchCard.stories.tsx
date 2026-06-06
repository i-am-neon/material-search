import type { Meta, StoryObj } from "@storybook/react";
import { MatchCard } from "./MatchCard";
import { matchesByRegion } from "../../demoData";

const sample = { ...matchesByRegion["terrazzo-floor"][0], similarity: 0.96 };

const meta: Meta<typeof MatchCard> = {
  title: "Studio/MatchCard",
  component: MatchCard,
  args: { match: sample, inCart: false, onToggleCart: () => {} },
  decorators: [(S) => <div style={{ width: 240, padding: 24 }}><S /></div>],
};
export default meta;
type Story = StoryObj<typeof MatchCard>;
export const Default: Story = {};
export const InSpecification: Story = { args: { inCart: true } };
