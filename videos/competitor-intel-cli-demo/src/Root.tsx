import "./index.css";
import { Composition } from "remotion";
import { CliDemoComposition } from "./Composition";
import { CLI_DURATION_IN_FRAMES } from "./cliDemoData";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="CliDemo"
        component={CliDemoComposition}
        durationInFrames={CLI_DURATION_IN_FRAMES}
        fps={30}
        width={1280}
        height={720}
      />
    </>
  );
};
