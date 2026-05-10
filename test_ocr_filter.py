from src.tools.screenshot_tools import is_likely_garbage

test_cases = [
    ('v hy fg alse alse FQQz', True),
    ('Se SR OR 文化 旅游', False),
    ('oR 具身 HB 精专 KX WR', True),
    ('CCM mn ROS F 5 we Bm oe ne', True),
    ('时政微纪录 古寨新歌总书记', False),
    ('我关了我开了我又关了我又开了', False),
    ('对话印权斌:历经15个月，我把', False),
    ('151件伊朗文物从战乱中运到中国', False),
    ('首页 时政 评论 视频', False),
    ('4K CCTV 直播 中国', False),
    ('ee ROLE', True),
    ('remap CN 151', False),
    ('LE 0 lh', True),
    ('ea RE ete', True),
    ('Pe re. HEA RGR a', True),
    ('om und as ae PMO', True),
    ('hr P 昌 mT AR', True),
    ('z ew 望海潮潮', False),
    ('vi 4 4, KY 我又关了', False),
    ('ape ig teats 封关之年', False),
]

print('测试垃圾检测:')
print('=' * 60)
correct = 0
for tc, expected in test_cases:
    result = is_likely_garbage(tc)
    status = '✓' if result == expected else '✗'
    if result == expected:
        correct += 1
    print(f'{status} {"垃圾" if result else "有效"}: {tc}')

print('=' * 60)
print(f'正确率: {correct}/{len(test_cases)} ({correct/len(test_cases)*100:.1f}%)')