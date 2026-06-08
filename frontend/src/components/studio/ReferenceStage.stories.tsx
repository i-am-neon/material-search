import type { Meta, StoryObj } from "@storybook/react";
import { ReferenceStage } from "./ReferenceStage";
import { regions } from "../../demoData";
import demoRoom from "../../assets/demo-room.png";

const meta: Meta<typeof ReferenceStage> = {
  title: "Studio/ReferenceStage",
  component: ReferenceStage,
  args: {
    previewUrl: demoRoom,
    imageWidth: 1536,
    imageHeight: 1024,
    regions,
    selectedRegionId: regions[0].id,
    onSelect: () => {},
  },
  decorators: [(S) => <div style={{ maxWidth: 520, padding: 24 }}><S /></div>],
};
export default meta;
type Story = StoryObj<typeof ReferenceStage>;
export const Default: Story = {};
