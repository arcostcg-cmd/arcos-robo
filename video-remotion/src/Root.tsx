import { CalculateMetadataFunction, Composition, staticFile } from "remotion";
import { DadosEp, Ep02 } from "./ep02/Ep02";

type Props = { arquivo: string; dados?: DadosEp };

const calcular: CalculateMetadataFunction<Props> = async ({ props }) => {
  const dados: DadosEp = await (await fetch(staticFile(props.arquivo))).json();
  return { durationInFrames: Math.ceil((dados.duracaoMs / 1000) * 30), props: { ...props, dados } };
};

const Ep: React.FC<Props> = ({ dados }) => (dados ? <Ep02 dados={dados} /> : null);

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Ep02Charizard"
      component={Ep}
      durationInFrames={900}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{ arquivo: "ep02.json" }}
      calculateMetadata={calcular}
    />
  );
};
