import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { segmentSam3, uploadSearchImage } from "../api";
import { Sam3Playground } from "./Sam3Playground";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    segmentSam3: vi.fn(),
    uploadSearchImage: vi.fn(),
  };
});

const segmentSam3Mock = vi.mocked(segmentSam3);
const uploadSearchImageMock = vi.mocked(uploadSearchImage);

describe("Sam3Playground", () => {
  beforeEach(() => {
    segmentSam3Mock.mockReset();
    uploadSearchImageMock.mockReset();
  });

  it("renders raw SAM3 regions and app overlay projection", () => {
    render(
      <MemoryRouter>
        <Sam3Playground
          initialPreviewUrl="room.png"
          initialResult={{
            model_id: "facebook/sam3",
            image_width: 320,
            image_height: 240,
            prompt: "chair",
            regions: [
              {
                id: "sam3_region_0",
                prompt: "chair",
                score: 0.93,
                box_xyxy: [10, 20, 110, 140],
              },
            ],
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("sam3_region_0")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /select region 1/i })).toHaveClass("region sel");
    expect(screen.getByText(/\"model_id\": \"facebook\/sam3\"/)).toBeInTheDocument();
  });

  it("posts image URL playground requests to the raw SAM3 endpoint", async () => {
    segmentSam3Mock.mockResolvedValue({
      model_id: "facebook/sam3",
      image_width: 320,
      image_height: 240,
      prompt: "wall panel",
      regions: [],
    });

    render(
      <MemoryRouter>
        <Sam3Playground />
      </MemoryRouter>,
    );

    await userEvent.type(screen.getByLabelText(/image url/i), "https://example.com/room.jpg");
    await userEvent.clear(screen.getByLabelText(/prompt/i));
    await userEvent.type(screen.getByLabelText(/prompt/i), "wall panel");
    await userEvent.click(screen.getByRole("button", { name: /run sam3/i }));

    expect(uploadSearchImageMock).not.toHaveBeenCalled();
    expect(segmentSam3Mock).toHaveBeenCalledWith({
      image_url: "https://example.com/room.jpg",
      prompt: "wall panel",
      confidence_threshold: 0.5,
      max_regions: 20,
      include_masks: true,
    });
  });
});
