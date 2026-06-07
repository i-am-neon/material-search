import type { Meta, StoryObj } from "@storybook/react";
import demoRoom from "../assets/demo-room.png";
import { Sam3Playground } from "./Sam3Playground";

const meta: Meta<typeof Sam3Playground> = {
  title: "Dev/Sam3Playground",
  component: Sam3Playground,
  args: {
    initialPreviewUrl: demoRoom,
    initialPrompt: "floor tile",
    initialResult: {
      model_id: "facebook/sam3",
      image_width: 1000,
      image_height: 800,
      prompt: "floor tile",
      regions: [
        {
          id: "sam3_region_0",
          prompt: "floor tile",
          score: 0.942,
          box_xyxy: [40, 560, 960, 790],
          mask: { format: "uncompressed_rle", size: [800, 1000], counts: [22, 9, 18, 11] },
        },
        {
          id: "sam3_region_1",
          prompt: "floor tile",
          score: 0.711,
          box_xyxy: [610, 370, 870, 590],
        },
      ],
    },
  },
};

export default meta;
type Story = StoryObj<typeof Sam3Playground>;

export const WithRawResult: Story = {};
