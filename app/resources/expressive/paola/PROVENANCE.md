# Eve voice reference

The reference combines two recordings donated by Paola to the Nabu Casa voice dataset for Italian. The dataset is released under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).

- [Nabu Casa voice dataset](https://github.com/OHF-Voice/voice-datasets#nabu-casa-voice-datasets)
- [Italian dataset at the source revision](https://huggingface.co/datasets/paolapersico1/Voice-Dataset-Italian/tree/2f6d1613f2388b58daf18aa7174eba53aeaa4f62)
- `wav/3000000001_3000000300_Chat/3000000062.wav` SHA-256 `2ebc4d2f2b98c13a905af2fc7680da97cba3672c84fe409e6060a2585f499489`
- `wav/3000000001_3000000300_Chat/3000000042.wav` SHA-256 `9a3b5a5f2b2497bf6d9f6d152585b6660425a452d654800860db28bd33cd02ea`

The reference combines those recordings in order and resamples them to 24 kHz mono PCM. SHA-256 of `reference.wav` is `a08bedfc8a025057993161e078d64f909ab4db8c90ff183cb5ebbcf4a65c6d37`.

The model is Qwen3-TTS Base 1.7B 8-bit, revision `e7dd0585652209fa0d7783659aad4e8a324de11c`. The runtime reads a local snapshot. Synthesis is performed on-device with network access denied.
