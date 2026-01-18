from model_layers import ModelLayersRegistry

if __name__ == '__main__':
    r = ModelLayersRegistry('model_layers.json')
    for key in ('qwen/qwen2.5-coder-14b','qwen2.5-coder-14b'):
        try:
            entry = r.get_layers_for_model(key)
            print(key, '=>', [l.id for l in entry])
        except Exception as e:
            print(key, 'error:', e)
